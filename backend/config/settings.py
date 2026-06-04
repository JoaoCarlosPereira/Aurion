"""Gerenciador de configurações (Config Manager).

Lê, valida, persiste e atualiza as configurações da aplicação usando
pydantic-settings, armazenando o estado em `config.json` no diretório do
projeto (estrutura da TechSpec Seção 4.2). Suporta:

- Leitura de `config.json` com fallback para valores padrão quando o arquivo
  não existe ou está vazio.
- Variáveis de ambiente com prefixo `AURION_` (delimitador aninhado `__`),
  ex.: `AURION_HERMES__ENDPOINT`.
- Atualização parcial (merge profundo) preservando valores não informados.
- Reset para os valores padrão.
- Serialização/desserialização JSON.

As dependências externas (áudio, STT, TTS, rede) não são tocadas aqui; este
módulo apenas gerencia o estado de configuração de forma assíncrona.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from config.models import (
    AppConfig,
    AudioConfig,
    DatabaseConfig,
    HermesConfig,
    STTConfig,
    TTSConfig,
    WakeWordConfig,
)

# Caminho padrão do arquivo de configuração (relativo ao diretório do projeto).
DEFAULT_CONFIG_PATH = "config.json"


class AurionSettings(BaseSettings):
    """Configuração da aplicação via pydantic-settings.

    Espelha os campos de `AppConfig` no nível raiz para permitir override por
    variáveis de ambiente com prefixo `AURION_` e delimitador aninhado `__`
    (ex.: `AURION_HERMES__ENDPOINT`).
    """

    model_config = SettingsConfigDict(
        env_prefix="AURION_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    database: DatabaseConfig = DatabaseConfig()
    hermes: HermesConfig = HermesConfig()
    stt: STTConfig = STTConfig()
    tts: TTSConfig = TTSConfig()
    wake_word: WakeWordConfig = WakeWordConfig()
    audio: AudioConfig = AudioConfig()

    def to_app_config(self) -> AppConfig:
        """Converte as settings carregadas em um `AppConfig` validado."""
        return AppConfig(
            database=self.database,
            hermes=self.hermes,
            stt=self.stt,
            tts=self.tts,
            wake_word=self.wake_word,
            audio=self.audio,
        )


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Mescla `updates` em `base` recursivamente, ignorando valores `None`.

    Dicionários aninhados são mesclados campo a campo; valores escalares e
    listas substituem o valor existente. Retorna um novo dicionário.
    """
    result = dict(base)
    for key, value in updates.items():
        if value is None:
            # Campos não informados em uma atualização parcial são ignorados.
            continue
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _diff(base: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Retorna os campos de `other` que diferem de `base` (recursivo).

    Usado para isolar apenas os valores sobrescritos por variáveis de ambiente
    em relação aos padrões, evitando que os padrões do ambiente sobreponham os
    valores lidos do arquivo de configuração.
    """
    result: dict[str, Any] = {}
    for key, value in other.items():
        base_value = base.get(key)
        if isinstance(value, dict) and isinstance(base_value, dict):
            nested = _diff(base_value, value)
            if nested:
                result[key] = nested
        elif value != base_value:
            result[key] = value
    return result


class ConfigManager:
    """Gerencia o ciclo de vida das configurações persistidas em JSON."""

    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self._config_path = Path(config_path)
        # Serializa escritas concorrentes ao arquivo de configuração.
        self._lock = asyncio.Lock()
        self._config: AppConfig | None = None

    @property
    def config_path(self) -> Path:
        return self._config_path

    def _load_from_disk(self) -> AppConfig:
        """Carrega a configuração do disco, com fallback para os padrões.

        Aplica overrides de variáveis de ambiente (prefixo `AURION_`) sobre os
        valores lidos do arquivo. Retorna um `AppConfig` válido mesmo quando o
        arquivo não existe ou está vazio.
        """
        file_data: dict[str, Any] = {}
        if self._config_path.exists():
            raw = self._config_path.read_text(encoding="utf-8").strip()
            if raw:
                file_data = json.loads(raw)

        # Precedência: padrões < arquivo < variáveis de ambiente.
        # Os overrides de ambiente (prefixo AURION_) são resolvidos por
        # pydantic-settings; comparamos com os padrões para extrair apenas os
        # campos efetivamente sobrescritos via ambiente.
        defaults = AppConfig().model_dump()
        env_config = AurionSettings().to_app_config().model_dump()
        env_overrides = _diff(defaults, env_config)

        merged = _deep_merge(defaults, file_data)
        merged = _deep_merge(merged, env_overrides)
        return AppConfig(**merged)

    def _write_to_disk(self, config: AppConfig) -> None:
        """Serializa a configuração para `config.json` (cria diretórios)."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def load(self) -> AppConfig:
        """Carrega (ou recarrega) a configuração do disco para a memória."""
        async with self._lock:
            self._config = await asyncio.to_thread(self._load_from_disk)
            return self._config

    async def get(self) -> AppConfig:
        """Retorna a configuração atual, carregando do disco se necessário."""
        if self._config is None:
            return await self.load()
        return self._config

    async def update(self, updates: dict[str, Any]) -> AppConfig:
        """Aplica uma atualização parcial (merge profundo) e persiste.

        `updates` deve conter apenas os campos a alterar (parcial ou total).
        Valores `None` são ignorados, preservando os existentes. A nova
        configuração é validada por Pydantic antes de ser escrita em disco.
        """
        async with self._lock:
            if self._config is None:
                self._config = await asyncio.to_thread(self._load_from_disk)
            merged = _deep_merge(self._config.model_dump(), updates)
            # Validação completa via Pydantic (tipos e faixas de valores).
            new_config = AppConfig(**merged)
            await asyncio.to_thread(self._write_to_disk, new_config)
            self._config = new_config
            return new_config

    async def reset(self) -> AppConfig:
        """Restaura todos os valores padrão e persiste em disco."""
        async with self._lock:
            new_config = AppConfig()
            await asyncio.to_thread(self._write_to_disk, new_config)
            self._config = new_config
            return new_config

    async def save(self) -> AppConfig:
        """Persiste a configuração atualmente em memória no disco."""
        async with self._lock:
            if self._config is None:
                self._config = await asyncio.to_thread(self._load_from_disk)
            await asyncio.to_thread(self._write_to_disk, self._config)
            return self._config


# --- Singleton de ciclo de vida da aplicação ---------------------------------

_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Retorna o singleton do Config Manager, exigindo init prévia."""
    if _config_manager is None:
        raise RuntimeError(
            "Config Manager não inicializado. Chame init_config_manager() na startup."
        )
    return _config_manager


async def init_config_manager(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> ConfigManager:
    """Inicializa o singleton do Config Manager e carrega a configuração."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    await _config_manager.load()
    return _config_manager


async def reset_config_manager() -> None:
    """Descarta o singleton (uso em testes e shutdown)."""
    global _config_manager
    _config_manager = None
