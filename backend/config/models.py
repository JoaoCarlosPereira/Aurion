"""Modelos Pydantic de configuração da aplicação.

Define todas as estruturas de configuração do Aurion conforme a TechSpec
(Seções 3.3 e 4.2): Hermes, STT, TTS (com TTS externo), wake word, áudio e
banco de dados. Todos os modelos usam Pydantic v2 com validação de tipos e
faixas de valores, e expõem valores padrão idênticos ao `config.json.example`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AnyUrl, BaseModel, Field


class DatabaseConfig(BaseModel):
    """Configuração do banco de dados SQLite (caminho do arquivo)."""

    # Caminho do arquivo SQLite. Mantido como string para aceitar caminhos
    # relativos ao diretório do projeto (ex.: "aurion.db").
    path: str = "aurion.db"


class HermesConfig(BaseModel):
    """Configuração de conexão com o Hermes Agent.

    O `auth_token` é sensível e NÃO deve ser exposto via API (ver TechSpec
    Seção 11); a camada de API mascara/omite esse campo no GET.
    """

    endpoint: str = "http://localhost:8080"
    auth_token: str = ""


class STTConfig(BaseModel):
    """Configuração do serviço de Speech-to-Text (whisper.cpp)."""

    engine: str = "whisper.cpp"
    model: str = "ggml-base-q4"
    language: str = "pt-BR"
    # Número de threads usadas pelo whisper.cpp (mínimo 1).
    threads: int = Field(default=2, ge=1)
    # Tamanho do beam search; 1 favorece latência mínima.
    beam_size: int = Field(default=1, ge=1)
    # Contexto máximo; -1 indica sem limite (comportamento padrão do whisper).
    max_context: int = Field(default=-1, ge=-1)


class ExternalTTSConfig(BaseModel):
    """Configuração do TTS externo opcional (endpoint HTTP com streaming)."""

    enabled: bool = False
    endpoint: str = "https://api.tts-provider.com/v1/synthesize"
    api_key: str = ""
    # Parâmetros enviados ao endpoint externo (input/voice/speed).
    params: dict[str, object] = Field(
        default_factory=lambda: {"input": "", "voice": "", "speed": 1.0}
    )
    format: str = "mp3"
    # Tempo limite em segundos para a requisição ao endpoint externo.
    timeout: int = Field(default=10, ge=1)


class TTSConfig(BaseModel):
    """Configuração do serviço de Text-to-Speech (edge-tts por padrão)."""

    engine: str = "edge-tts"
    voice: str = "pt-BR-FabioNeural"
    # Ajuste de velocidade relativo (percentual) aplicado ao edge-tts.
    rate: int = 0
    # Volume em percentual (0 a 100).
    volume: int = Field(default=100, ge=0, le=100)
    external: ExternalTTSConfig = Field(default_factory=ExternalTTSConfig)


class WakeWordConfig(BaseModel):
    """Configuração do motor de detecção de wake word (Porcupine)."""

    engine: str = "porcupine"
    # Sensibilidade de detecção entre 0.0 e 1.0 (padrão 0.5 para PT-BR).
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    keyword: str = "aurion"
    keyword_path: str | None = None
    access_key: str | None = None
    wake_word_timeout: int = Field(default=10, ge=1)


class AudioConfig(BaseModel):
    """Configuração de captura de áudio (PyAudio)."""

    # Taxa de amostragem em Hz; whisper.cpp opera a 16000 Hz.
    sample_rate: int = Field(default=16000, ge=8000)
    # Número de canais (mono por padrão).
    channels: int = Field(default=1, ge=1)
    # Tamanho do bloco de leitura do stream de áudio (em frames).
    chunk_size: int = Field(default=1024, ge=1)
    # Limiar de silêncio para detecção de fim de fala (VAD).
    silence_threshold: int = Field(default=300, ge=0)
    # Tempo máximo (s) aguardando fala após detecção do wake word.
    wake_word_timeout: int = Field(default=10, ge=1)


class AppConfig(BaseModel):
    """Configuração raiz da aplicação, agregando todas as sub-configurações."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    hermes: HermesConfig = Field(default_factory=HermesConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)


# --- Modelos de atualização parcial (PUT) ------------------------------------
# Todos os campos opcionais para permitir merge parcial sem sobrescrever valores
# não informados. Usados pela camada de API ao validar o corpo do PUT.


class DatabaseConfigUpdate(BaseModel):
    """Atualização parcial da configuração de banco de dados."""

    path: str | None = None


class HermesConfigUpdate(BaseModel):
    """Atualização parcial da configuração do Hermes."""

    endpoint: str | None = None
    auth_token: str | None = None


class STTConfigUpdate(BaseModel):
    """Atualização parcial da configuração de STT."""

    engine: str | None = None
    model: str | None = None
    language: str | None = None
    threads: int | None = Field(default=None, ge=1)
    beam_size: int | None = Field(default=None, ge=1)
    max_context: int | None = Field(default=None, ge=-1)


class ExternalTTSConfigUpdate(BaseModel):
    """Atualização parcial da configuração de TTS externo."""

    enabled: bool | None = None
    endpoint: str | None = None
    api_key: str | None = None
    params: dict[str, object] | None = None
    format: str | None = None
    timeout: int | None = Field(default=None, ge=1)


class TTSConfigUpdate(BaseModel):
    """Atualização parcial da configuração de TTS."""

    engine: str | None = None
    voice: str | None = None
    rate: int | None = None
    volume: int | None = Field(default=None, ge=0, le=100)
    external: ExternalTTSConfigUpdate | None = None


class WakeWordConfigUpdate(BaseModel):
    """Atualização parcial da configuração de wake word."""

    engine: str | None = None
    sensitivity: float | None = Field(default=None, ge=0.0, le=1.0)
    keyword: str | None = None
    keyword_path: str | None = None
    access_key: str | None = None
    wake_word_timeout: int | None = Field(default=None, ge=1)


class AudioConfigUpdate(BaseModel):
    """Atualização parcial da configuração de áudio."""

    sample_rate: int | None = Field(default=None, ge=8000)
    channels: int | None = Field(default=None, ge=1)
    chunk_size: int | None = Field(default=None, ge=1)
    silence_threshold: int | None = Field(default=None, ge=0)
    wake_word_timeout: int | None = Field(default=None, ge=1)


class AppConfigUpdate(BaseModel):
    """Corpo de atualização parcial/total da configuração (PUT /api/config)."""

    database: DatabaseConfigUpdate | None = None
    hermes: HermesConfigUpdate | None = None
    stt: STTConfigUpdate | None = None
    tts: TTSConfigUpdate | None = None
    wake_word: WakeWordConfigUpdate | None = None
    audio: AudioConfigUpdate | None = None
