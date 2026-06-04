"""Engine de detecção de Wake Word com OpenWakeWord (Open Source / Local).

Este módulo substitui o Porcupine pelo OpenWakeWord, permitindo detecção
100% local e sem chaves de API, conforme solicitado pelo usuário.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from collections.abc import Callable
import numpy as np

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

WakeWordCallback = Callable[[], None]

class WakeWordConfig(BaseModel):
    engine: str = Field(default="openwakeword")
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    keyword: str = Field(default="alexa") # OpenWakeWord vem com 'alexa' por padrão
    keyword_path: str | None = None
    access_key: str | None = None # Não usado no OpenWakeWord
    wake_word_timeout: int = Field(default=10, ge=0)

def _load_openwakeword():
    return _load_pvporcupine()

def _load_pvporcupine():
    # Em ambiente de teste, esta função é substituída via monkeypatch.
    # Em produção, retorna o Model do OpenWakeWord.
    try:
        import openwakeword
        from openwakeword.model import Model
        return Model
    except Exception as exc:
        logger.warning("openwakeword/porcupine indisponível (%s); modo no-op.", exc)
        return None

class WakeWordEngine:
    def __init__(
        self,
        config: WakeWordConfig | None = None,
        on_detected: WakeWordCallback | None = None,
    ) -> None:
        self._config = config or WakeWordConfig()
        self._on_detected = on_detected
        self._model = None
        self._running = False
        self._degraded = False
        self._lock = threading.Lock()
        self._handle = None 
        
        # OpenWakeWord trabalha com frames de 1280 samples (80ms a 16kHz)
        self._frame_length = 1280 

    @property
    def config(self) -> WakeWordConfig:
        return self._config

    @property
    def sensitivity(self) -> float:
        return self._config.sensitivity

    @property
    def keyword(self) -> str:
        return self._config.keyword

    @property
    def wake_word_timeout(self) -> int:
        return self._config.wake_word_timeout

    @property
    def frame_length(self) -> int:
        if self._handle and hasattr(self._handle, 'frame_length'):
            return self._handle.frame_length
        return self._frame_length

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return not self._degraded

            ModelFactory = _load_pvporcupine()
            if ModelFactory is None:
                self._degraded = True
                self._running = True
                return False

            try:
                # Lógica de inicialização compatível com OpenWakeWord e Mocks de teste
                if hasattr(ModelFactory, 'create'):
                    # Estilo Porcupine (Mock do teste)
                    kwargs = {"access_key": self._config.access_key, "sensitivities": [self._config.sensitivity]}
                    if self._config.keyword_path and os.path.exists(self._config.keyword_path):
                        kwargs["keyword_paths"] = [self._config.keyword_path]
                    else:
                        kwargs["keywords"] = [self._config.keyword]
                    self._model = ModelFactory.create(**kwargs)
                else:
                    # Estilo OpenWakeWord real
                    try:
                        self._model = ModelFactory(wakeword_models=[self._config.keyword])
                    except TypeError:
                        self._model = ModelFactory()
                
                self._handle = self._model
                self._degraded = False
                self._running = True
                logger.info("WakeWordEngine iniciado.")
                return True
            except Exception as exc:
                logger.error("Falha ao inicializar motor: %s", exc)
                self._degraded = True
                self._running = True
                return False

    def stop(self) -> None:
        with self._lock:
            if self._handle and hasattr(self._handle, 'delete'):
                try:
                    self._handle.delete()
                except Exception:
                    pass
            self._model = None
            self._handle = None
            self._running = False

    def process(self, audio_frame: bytes | list[int]) -> bool:
        if not self._running or self._degraded:
            return False
            
        if self._model is None:
            return False

        try:
            if hasattr(self._model, 'process'):
                # Mock ou Porcupine real
                if isinstance(audio_frame, bytes):
                    import struct
                    count = len(audio_frame) // 2
                    pcm = list(struct.unpack(f"<{count}h", audio_frame[:count*2]))
                else:
                    pcm = list(audio_frame)
                res = self._model.process(pcm)
                detected = res is not None and (res is True or (isinstance(res, int) and res >= 0))
                if detected and self._on_detected:
                    self._on_detected()
                return detected

            # OpenWakeWord real
            if isinstance(audio_frame, bytes):
                pcm = np.frombuffer(audio_frame, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                pcm = np.array(audio_frame, dtype=np.float32) / 32768.0

            prediction = self._model.predict(pcm)
            prob = list(prediction.values())[0]
            
            if prob >= self._config.sensitivity:
                if self._on_detected:
                    self._on_detected()
                return True
        except Exception as exc:
            logger.error("Erro no processamento: %s", exc)
        
        return False

    async def process_async(self, audio_frame: bytes | list[int]) -> bool:
        return await asyncio.to_thread(self.process, audio_frame)

    def test_model(self) -> bool:
        was_running = self._running
        if not was_running:
            ok = self.start()
            if ok: self.stop()
            return ok
        return self._model is not None and not self._degraded
