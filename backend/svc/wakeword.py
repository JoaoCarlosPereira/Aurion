"""Engine de detecção de Wake Word ("Aurion") com Porcupine (Picovoice).

Este módulo implementa o motor de detecção da palavra de ativação "Aurion" que
opera continuamente sobre o stream de áudio capturado pelo PyAudio (16kHz, 1
canal), conforme a TechSpec (Seção 5.2) e a ADR-002.

Pontos de projeto:

- **Import lazy do `pvporcupine`**: a biblioteca nativa não está disponível em
  todos os ambientes (ex.: CI/testes). O import é feito sob demanda dentro de
  uma função; quando indisponível, o engine degrada graciosamente para um modo
  no-op que loga o problema e *nunca* detecta a wake word (TechSpec Seção 10:
  "Wake word falha → log de erro, serviço continua em modo idle").
- **Interface assíncrona/threaded**: o processamento de cada frame é uma
  operação de CPU rápida, mas é exposta de forma assíncrona
  (`process_async`) executando em um *thread pool* para não bloquear o event
  loop do FastAPI. Há também o método síncrono `process` para uso direto dentro
  da thread dedicada do Listening Service.
- **Callback de detecção**: ao detectar "Aurion", o engine pode invocar um
  callback opcional fornecido na construção.
- **Sensibilidade configurável**: validada no intervalo [0.0, 1.0] (padrão 0.5).
- **Timeout de escuta**: tempo (s) para voltar ao modo escuta após uma detecção
  sem fala subsequente (padrão 10s); exposto como propriedade para o Listening
  Service consumir.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Tipo do callback chamado quando a wake word é detectada (sem argumentos).
WakeWordCallback = Callable[[], None]


class WakeWordConfig(BaseModel):
    """Configuração do engine de wake word (espelha `config.json`).

    Mantida localmente neste módulo para evitar acoplamento com o Config Manager
    (que é responsabilidade de outra tarefa). O Listening Service / Config
    Manager pode construir esta instância a partir das configurações persistidas.
    """

    engine: str = Field(default="porcupine", description="Engine de wake word.")
    sensitivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sensibilidade da detecção, no intervalo [0.0, 1.0].",
    )
    keyword: str = Field(default="aurion", description="Palavra de ativação.")
    # Caminho do modelo .ppn personalizado (pronúncia brasileira de "Aurion").
    # Quando None ou inexistente, faz-se fallback para a keyword embutida.
    keyword_path: str | None = Field(
        default=None,
        description="Caminho do arquivo .ppn personalizado para 'Aurion'.",
    )
    # Caminho do access key da Picovoice (obrigatório pelo Porcupine moderno).
    access_key: str | None = Field(
        default=None,
        description="Access key da Picovoice para inicializar o Porcupine.",
    )
    # Timeout (s) para voltar ao modo escuta após detecção sem fala (TechSpec 5.2).
    wake_word_timeout: int = Field(
        default=10,
        ge=0,
        description="Tempo (s) para retornar ao modo escuta após detecção.",
    )


def _load_pvporcupine():
    """Importa o `pvporcupine` de forma lazy.

    Retorna o módulo importado ou `None` caso a biblioteca não esteja
    disponível no ambiente (degradação graciosa).
    """
    try:
        import pvporcupine  # type: ignore

        return pvporcupine
    except Exception as exc:  # noqa: BLE001 — qualquer falha de import degrada.
        logger.warning(
            "pvporcupine indisponível (%s); wake word operará em modo no-op.",
            exc,
        )
        return None


class WakeWordEngine:
    """Motor de detecção da wake word "Aurion" usando Porcupine.

    Quando o `pvporcupine` está disponível e inicializa corretamente, processa
    frames de áudio PCM (int16, 16kHz, mono) e detecta a palavra de ativação.
    Caso contrário, opera em modo no-op: nunca detecta, apenas registra logs.
    """

    def __init__(
        self,
        config: WakeWordConfig | None = None,
        on_detected: WakeWordCallback | None = None,
    ) -> None:
        """Cria o engine sem inicializar o Porcupine (use `start()` para isso).

        Args:
            config: configuração do wake word; usa os padrões se omitida.
            on_detected: callback opcional invocado a cada detecção.
        """
        self._config = config or WakeWordConfig()
        self._on_detected = on_detected
        # Handle do Porcupine quando inicializado; None em modo no-op/parado.
        self._handle = None
        self._running = False
        # Indica se a degradação graciosa foi acionada (modo no-op).
        self._degraded = False
        # Protege start/stop/process contra concorrência entre threads.
        self._lock = threading.Lock()

    # --- Propriedades de configuração ----------------------------------------

    @property
    def config(self) -> WakeWordConfig:
        """Configuração atual do engine."""
        return self._config

    @property
    def sensitivity(self) -> float:
        """Sensibilidade configurada (intervalo [0.0, 1.0])."""
        return self._config.sensitivity

    @property
    def keyword(self) -> str:
        """Palavra de ativação configurada."""
        return self._config.keyword

    @property
    def wake_word_timeout(self) -> int:
        """Timeout (s) para retornar ao modo escuta após uma detecção."""
        return self._config.wake_word_timeout

    @property
    def is_running(self) -> bool:
        """Indica se o engine está iniciado (Porcupine ativo ou modo no-op)."""
        return self._running

    @property
    def is_degraded(self) -> bool:
        """Indica se o engine está em modo no-op (Porcupine indisponível)."""
        return self._degraded

    @property
    def frame_length(self) -> int:
        """Número de samples por frame esperado pelo Porcupine.

        Quando o Porcupine não está ativo, retorna o padrão histórico (512).
        """
        if self._handle is not None:
            return int(getattr(self._handle, "frame_length", 512))
        return 512

    @property
    def sample_rate(self) -> int:
        """Taxa de amostragem esperada (16kHz, conforme config de áudio)."""
        if self._handle is not None:
            return int(getattr(self._handle, "sample_rate", 16000))
        return 16000

    # --- Resolução do modelo --------------------------------------------------

    def _resolve_keyword_args(self, pvporcupine) -> dict:
        """Monta os argumentos de keyword para `pvporcupine.create`.

        Faz fallback para a keyword embutida quando o arquivo .ppn personalizado
        não existe (TechSpec / subtarefa de fallback para modelo padrão).
        """
        path = self._config.keyword_path
        if path and Path(path).is_file():
            logger.info("Carregando modelo .ppn personalizado: %s", path)
            return {"keyword_paths": [path]}

        if path:
            logger.warning(
                "Modelo .ppn '%s' não encontrado; usando keyword embutida '%s'.",
                path,
                self._config.keyword,
            )
        # Fallback: usa uma keyword embutida do Porcupine. A keyword configurada
        # ("aurion") pode não existir nas embutidas; nesse caso o Porcupine
        # levantará erro, tratado em start() com degradação graciosa.
        keywords = self._available_builtin_keyword(pvporcupine)
        return {"keywords": [keywords]}

    def _available_builtin_keyword(self, pvporcupine) -> str:
        """Escolhe uma keyword embutida válida como fallback.

        Prefere a keyword configurada se ela constar entre as embutidas;
        caso contrário, usa a primeira embutida disponível.
        """
        builtin = set(getattr(pvporcupine, "KEYWORDS", []) or [])
        if self._config.keyword in builtin:
            return self._config.keyword
        if builtin:
            return sorted(builtin)[0]
        # Sem lista de embutidas: devolve a keyword configurada e deixa o
        # Porcupine validar.
        return self._config.keyword

    # --- Ciclo de vida --------------------------------------------------------

    def start(self) -> bool:
        """Inicializa o Porcupine (idempotente).

        Returns:
            True se o engine ficou operacional (Porcupine ativo).
            False se entrou em modo no-op (degradação graciosa).
        """
        with self._lock:
            if self._running:
                return not self._degraded

            pvporcupine = _load_pvporcupine()
            if pvporcupine is None:
                # Biblioteca indisponível: modo no-op.
                self._degraded = True
                self._running = True
                self._handle = None
                return False

            try:
                keyword_args = self._resolve_keyword_args(pvporcupine)
                self._handle = pvporcupine.create(
                    access_key=self._config.access_key,
                    sensitivities=[self._config.sensitivity],
                    **keyword_args,
                )
                self._degraded = False
                self._running = True
                logger.info(
                    "WakeWordEngine iniciado (keyword=%s, sensibilidade=%.2f).",
                    self._config.keyword,
                    self._config.sensitivity,
                )
                return True
            except Exception as exc:  # noqa: BLE001 — degradação graciosa.
                logger.error(
                    "Falha ao inicializar Porcupine (%s); modo no-op ativado.",
                    exc,
                )
                self._handle = None
                self._degraded = True
                self._running = True
                return False

    def stop(self) -> None:
        """Libera os recursos do Porcupine e para o engine (idempotente)."""
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.delete()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Erro ao liberar Porcupine: %s", exc)
                finally:
                    self._handle = None
            self._running = False
            self._degraded = False

    # --- Processamento --------------------------------------------------------

    def _decode_frame(self, audio_frame: bytes | list[int]):
        """Converte um frame em uma lista de samples int16 esperada pelo Porcupine.

        Aceita `bytes` (PCM little-endian int16) ou uma sequência de ints já
        decodificada.
        """
        if isinstance(audio_frame, (bytes, bytearray)):
            import struct

            count = len(audio_frame) // 2
            return list(struct.unpack(f"<{count}h", bytes(audio_frame[: count * 2])))
        return list(audio_frame)

    def process(self, audio_frame: bytes | list[int]) -> bool:
        """Processa um frame de áudio e indica se a wake word foi detectada.

        Em modo no-op (Porcupine indisponível), sempre retorna False.

        Args:
            audio_frame: frame PCM int16 (bytes little-endian) ou lista de ints.

        Returns:
            True se "Aurion" foi detectada neste frame; False caso contrário.
        """
        if not self._running:
            logger.debug("process() chamado com engine parado; ignorando frame.")
            return False
        if self._handle is None:
            # Modo no-op: nunca detecta.
            return False

        try:
            pcm = self._decode_frame(audio_frame)
            # Porcupine retorna o índice da keyword detectada (>= 0) ou -1.
            result = self._handle.process(pcm)
        except Exception as exc:  # noqa: BLE001 — não derruba o loop de escuta.
            logger.error("Erro ao processar frame de áudio: %s", exc)
            return False

        detected = result is not None and result >= 0
        if detected:
            logger.info("Wake word 'Aurion' detectada.")
            self._fire_callback()
        return detected

    async def process_async(self, audio_frame: bytes | list[int]) -> bool:
        """Versão assíncrona de `process`, executada em thread pool.

        Permite consumir o engine a partir de código async (ex.: handlers do
        FastAPI) sem bloquear o event loop, já que o `pvporcupine.process` é
        uma chamada síncrona/CPU-bound.
        """
        return await asyncio.to_thread(self.process, audio_frame)

    def _fire_callback(self) -> None:
        """Invoca o callback de detecção, se configurado, sem propagar exceções."""
        if self._on_detected is None:
            return
        try:
            self._on_detected()
        except Exception as exc:  # noqa: BLE001 — callback não pode derrubar o engine.
            logger.error("Callback de wake word falhou: %s", exc)

    # --- Diagnóstico ----------------------------------------------------------

    def test_model(self) -> bool:
        """Valida o carregamento do modelo inicializando e liberando o Porcupine.

        Útil para o endpoint de teste de configuração. Preserva o estado atual
        do engine: se estava parado, volta a ficar parado ao final.

        Returns:
            True se o modelo carrega e o Porcupine fica operacional;
            False se houve degradação (Porcupine indisponível ou erro).
        """
        was_running = self._running
        had_handle = self._handle is not None

        if not was_running:
            ok = self.start()
            self.stop()
            return ok

        # Já estava iniciado: o sucesso depende de ter um handle ativo.
        return had_handle and not self._degraded
