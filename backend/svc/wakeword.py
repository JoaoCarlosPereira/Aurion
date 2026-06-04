"""Engine de detecção de Wake Word com Vosk (Open Source / Local).

Este módulo usa o Vosk para detecção de wake word "aurion" de forma
100% local, gratuita e sem chaves de API. Usa gramática customizada para
restringir o reconhecimento apenas à palavra "aurion", melhorando precisão
e reduzindo falsos positivos.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

WakeWordCallback = Callable[[], None]


class WakeWordConfig(BaseModel):
    """Configuração do engine de wake word com Vosk."""

    engine: str = Field(default="vosk")
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0, description="Threshold de confiança")
    keyword: str = Field(default="aurion")
    model_path: str | None = None
    access_key: str | None = None
    wake_word_timeout: int = Field(default=10, ge=0)


def _load_vosk():
    """Importa o módulo Vosk de forma lazy.

    Retorna o módulo importado ou None caso não esteja disponível.
    """
    try:
        import vosk  # type: ignore
        from vosk import Model  # noqa: F401

        return vosk
    except Exception as exc:
        logger.warning("vosk indisponível (%s); wake word operará em modo no-op.", exc)
        return None


class WakeWordEngine:
    """Motor de detecção da wake word "aurion" usando Vosk.

    Usa o Vosk em modo grammar com a palavra "aurion" como único termo esperado.
    Isso reduz significativamente falsos positivos comparado ao modo full transcription.
    """

    def __init__(
        self,
        config: WakeWordConfig | None = None,
        on_detected: WakeWordCallback | None = None,
    ) -> None:
        self._config = config or WakeWordConfig()
        self._on_detected = on_detected
        self._model = None
        self._recognizer = None
        self._running = False
        self._degraded = False
        self._lock = threading.Lock()
        # Vosk usa frames de 1600 samples (100ms a 16kHz)
        self._frame_length = 1600

    # --- Propriedades --------------------------------------------------------

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
    def frame_length(self) -> int:
        """Tamanho do frame esperado pelo Vosk."""
        return self._frame_length

    @property
    def sample_rate(self) -> int:
        """Taxa de amostragem esperada (16kHz)."""
        return 16000

    @property
    def is_running(self) -> bool:
        """Indica se o engine está iniciado."""
        return self._running

    @property
    def is_degraded(self) -> bool:
        """Indica se o engine está em modo no-op."""
        return self._degraded

    # --- Ciclo de vida -------------------------------------------------------

    def start(self) -> bool:
        """Inicia o motor Vosk com gramática para a wake word.

        Returns:
            True se inicializado com sucesso, False em caso de falha (degrada).
        """
        with self._lock:
            if self._running:
                return not self._degraded

            vosk_module = _load_vosk()
            if vosk_module is None:
                self._degraded = True
                self._running = True
                return False

            try:
                from vosk import Model as VoskModel  # noqa: N812

                # Carrega o modelo Vosk
                model_path = self._config.model_path or "vosk-model-small-pt-0.3"
                self._model = VoskModel(model_path)

                # Cria reconhecedor com gramática da wake word
                grammar_json = json.dumps([self._config.keyword, "[unk]"])
                self._recognizer = vosk_module.KaldiRecognizer(
                    self._model, 16000, grammar_json
                )

                self._degraded = False
                self._running = True
                logger.info(
                    "WakeWordEngine (Vosk) iniciado com keyword '%s'.",
                    self._config.keyword,
                )
                return True

            except Exception as exc:  # noqa: BLE001
                logger.error("Falha ao inicializar motor Vosk (%s): %s", type(exc).__name__, exc)
                self._degraded = True
                self._running = True
                return False

    def stop(self) -> None:
        """Para o engine."""
        with self._lock:
            if self._model is not None:
                del self._model
            self._model = None
            self._recognizer = None
            self._running = False
            self._degraded = False

    # --- Processamento -------------------------------------------------------

    def process(self, audio_frame: bytes | list[int]) -> bool:
        """Processa um frame de áudio e verifica se a wake word foi detectada.

        Args:
            audio_frame: frame PCM int16 (bytes little-endian) ou lista de ints.

        Returns:
            True se "aurion" foi detectada neste frame.
        """
        if not self._running or self._degraded:
            return False

        if self._recognizer is None:
            return False

        try:
            if isinstance(audio_frame, bytes):
                accepted = self._recognizer.AcceptWaveform(audio_frame)
            else:
                # Converte lista de ints para bytes PCM
                import struct

                count = len(audio_frame) // 2
                pcm_bytes = struct.pack(f"<{count}h", *audio_frame[: count * 2])
                accepted = self._recognizer.AcceptWaveform(pcm_bytes)

            if accepted:
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "").strip().lower()
                if text and self._is_wake_word(text):
                    logger.info("Wake word '%s' detectada: %s", self._config.keyword, text)
                    self._fire_callback()
                    return True

        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao processar frame Vosk: %s", exc)

        return False

    def _is_wake_word(self, text: str) -> bool:
        """Verifica se o texto transcrevado contém a wake word."""
        if text == self._config.keyword:
            return True
        # Fuzzy: aceita se a keyword estiver contida no texto
        return self._config.keyword in text

    def _fire_callback(self) -> None:
        """Invoca o callback de detecção."""
        if self._on_detected is None:
            return
        try:
            self._on_detected()
        except Exception as exc:  # noqa: BLE001
            logger.error("Callback de wake word falhou: %s", exc)

    async def process_async(self, audio_frame: bytes | list[int]) -> bool:
        """Versão assíncrona de process(), executada em thread pool."""
        return await asyncio.to_thread(self.process, audio_frame)

    def test_model(self) -> bool:
        """Valida o carregamento do modelo Vosk.

        Returns:
            True se o modelo carrega corretamente.
        """
        was_running = self._running
        if not was_running:
            ok = self.start()
            if ok:
                self.stop()
            return ok
        return self._recognizer is not None and not self._degraded
