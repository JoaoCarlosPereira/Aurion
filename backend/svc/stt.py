"""Serviço STT (Speech-to-Text) baseado em whisper.cpp.

Converte áudio capturado pelo Listening Service (PCM 16kHz, mono) em texto
PT-BR usando whisper.cpp via os bindings Python `whispercpp`. O serviço força
o idioma para `pt` (reduzindo latência e aumentando precisão), aplica as
otimizações configuráveis (threads, beam_size, max_context) e degrada
graciosamente quando o whisper.cpp não está disponível, conforme a TechSpec
(Seções 5.3 e 10) e a ADR-002.

O import do `whispercpp` é preguiçoso (lazy): o módulo é carregável e testável
mesmo em ambientes sem o binário/biblioteca instalada. Quando o transcritor não
pode ser carregado, o serviço aciona o fallback (engine alternativa) ou retorna
texto vazio em vez de levantar exceções, mantendo o pipeline de voz operante.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Taxa de amostragem esperada do áudio de entrada (16kHz), conforme TechSpec 5.3.
SAMPLE_RATE = 16000


class STTConfig(BaseModel):
    """Configuração do serviço STT (espelha o bloco `stt` do config.json).

    Mantida local ao módulo para que o serviço seja autossuficiente enquanto o
    Config Manager (task_03) não estiver disponível. Os campos seguem a TechSpec
    (Seção 4.2) e o `config.json.example`.
    """

    engine: str = "whisper.cpp"
    model: str = "ggml-base-q4"
    language: str = "pt-BR"
    threads: int = Field(default=2, ge=1)
    beam_size: int = Field(default=1, ge=1)
    max_context: int = -1
    # Tempo máximo (segundos) para concluir uma transcrição antes de abortar.
    timeout: float = Field(default=30.0, gt=0)
    # Engine alternativa usada quando o whisper.cpp falha (degradação graciosa).
    fallback_engine: str | None = None
    # Janela mínima de áudio (segundos) acumulada antes de transcrever (buffer 1-2s).
    min_buffer_seconds: float = Field(default=1.0, ge=0)


@runtime_checkable
class Transcriber(Protocol):
    """Contrato mínimo de um transcritor (permite mockar nos testes).

    Implementações reais encapsulam o whisper.cpp; nos testes, um objeto simples
    que exponha `transcribe(audio: np.ndarray) -> str` satisfaz este protocolo.
    """

    def transcribe(self, audio: np.ndarray) -> str:  # pragma: no cover - protocolo
        ...


def _to_float32_pcm(audio_data: bytes | np.ndarray) -> np.ndarray:
    """Normaliza o áudio de entrada para `np.ndarray` float32 em [-1.0, 1.0].

    Aceita `bytes` (PCM 16-bit little-endian, como produzido pelo PyAudio) ou um
    `np.ndarray` já decodificado (int16 ou float). O whisper.cpp espera amostras
    float32 mono normalizadas.
    """
    if isinstance(audio_data, bytes):
        # PCM 16-bit assinado -> float32 normalizado.
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        return samples / 32768.0

    array = np.asarray(audio_data)
    if array.dtype == np.float32:
        return array
    if np.issubdtype(array.dtype, np.integer):
        return array.astype(np.float32) / 32768.0
    return array.astype(np.float32)


def _is_silence(audio: np.ndarray, threshold: float = 1e-4) -> bool:
    """Detecta silêncio comparando a energia (RMS) do sinal com um limiar."""
    if audio.size == 0:
        return True
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    return rms < threshold


class STTService:
    """Serviço de transcrição de fala em texto com whisper.cpp.

    Carrega o transcritor de forma preguiçosa na primeira transcrição (ou via
    `test_model()`). Em caso de indisponibilidade do whisper.cpp, tenta a engine
    de fallback configurada; persistindo a falha, retorna texto vazio sem
    propagar a exceção (degradação graciosa).
    """

    def __init__(
        self,
        config: STTConfig | None = None,
        transcriber: Transcriber | None = None,
    ) -> None:
        """Inicializa o serviço.

        `transcriber` permite injeção (usado nos testes); quando ausente, o
        whisper.cpp é carregado preguiçosamente na primeira utilização.
        """
        self._config = config or STTConfig()
        self._transcriber: Transcriber | None = transcriber
        # Indica que já tentamos carregar o transcritor (evita recargas repetidas
        # quando o carregamento falha de forma persistente).
        self._load_attempted = transcriber is not None

    @property
    def config(self) -> STTConfig:
        return self._config

    def _load_whisper(self) -> Transcriber | None:
        """Carrega o whisper.cpp com import preguiçoso e otimizações da config.

        Retorna `None` (sem levantar) quando o módulo não está disponível ou o
        modelo não pode ser carregado, permitindo o acionamento do fallback.
        """
        try:
            # Import preguiçoso: a dependência pode não existir no ambiente.
            from whispercpp import Whisper  # type: ignore[import-not-found]
        except Exception as exc:  # ModuleNotFoundError e afins.
            logger.warning(
                "whisper.cpp indisponível (import falhou): %s", exc
            )
            return None

        try:
            # Carrega o modelo configurado (ex.: ggml-base-q4) e aplica os
            # parâmetros de idioma/performance suportados pelos bindings.
            whisper = Whisper.from_pretrained(self._config.model)
            params = getattr(whisper, "params", None)
            if params is not None:
                # Força idioma PT-BR ("pt") e aplica otimizações configuráveis.
                _apply_whisper_params(params, self._config)
            return whisper
        except Exception as exc:
            logger.error(
                "Falha ao carregar o modelo whisper.cpp '%s': %s",
                self._config.model,
                exc,
            )
            return None

    def _load_fallback(self) -> Transcriber | None:
        """Carrega a engine de fallback, quando configurada.

        Implementação placeholder: o fallback real (ex.: Vosk) será fornecido em
        tarefas futuras. Aqui apenas registramos a tentativa e retornamos `None`,
        deixando o serviço degradar para texto vazio.
        """
        if not self._config.fallback_engine:
            return None
        logger.warning(
            "Engine STT primária indisponível; fallback '%s' não implementado.",
            self._config.fallback_engine,
        )
        return None

    def _ensure_transcriber(self) -> Transcriber | None:
        """Garante um transcritor carregado, tentando whisper e depois fallback."""
        if self._transcriber is not None:
            return self._transcriber
        if self._load_attempted:
            return None

        self._load_attempted = True
        self._transcriber = self._load_whisper()
        if self._transcriber is None:
            self._transcriber = self._load_fallback()
        return self._transcriber

    def _run_transcription(self, audio: np.ndarray) -> str:
        """Executa a transcrição síncrona no transcritor carregado."""
        transcriber = self._ensure_transcriber()
        if transcriber is None:
            # Degradação graciosa: nenhuma engine disponível.
            return ""
        text = transcriber.transcribe(audio)
        return (text or "").strip()

    async def transcribe(self, audio_data: bytes | np.ndarray) -> str:
        """Transcreve áudio 16kHz para texto PT-BR (assíncrono).

        Aceita `bytes` (PCM 16-bit do PyAudio) ou `np.ndarray`. Retorna o texto
        reconhecido; retorna string vazia para silêncio, buffer insuficiente ou
        quando nenhuma engine STT está disponível. Respeita o `timeout` da
        config e nunca propaga exceções de transcrição (degradação graciosa).
        """
        audio = _to_float32_pcm(audio_data)

        # Buffer mínimo (1-2s): se o áudio for menor que a janela configurada,
        # não há sinal suficiente para uma transcrição confiável.
        min_samples = int(self._config.min_buffer_seconds * SAMPLE_RATE)
        if audio.size < min_samples:
            return ""

        # Silêncio -> texto vazio (evita "alucinações" do whisper em ruído baixo).
        if _is_silence(audio):
            return ""

        try:
            # whisper.cpp é CPU-bound e síncrono: executa em thread separada para
            # não bloquear o event loop, com timeout configurável.
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_transcription, audio),
                timeout=self._config.timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Timeout (%.1fs) excedido na transcrição STT.",
                self._config.timeout,
            )
            return ""
        except Exception as exc:
            logger.error("Erro inesperado na transcrição STT: %s", exc)
            return ""

    async def test_model(self) -> bool:
        """Valida o carregamento do modelo STT.

        Retorna `True` se um transcritor (whisper.cpp ou fallback) pôde ser
        carregado; `False` caso contrário. Usado pelo endpoint `POST /api/test/stt`.
        """
        transcriber = await asyncio.to_thread(self._ensure_transcriber)
        return transcriber is not None


def _apply_whisper_params(params: object, config: STTConfig) -> None:
    """Aplica idioma e otimizações aos parâmetros do whisper.cpp, se suportados.

    Os bindings expõem atributos como `language`, `n_threads`, `beam_search` e
    `max_context`. Usamos `setattr` defensivo (com `hasattr`) porque a superfície
    exata da API varia entre versões do `whispercpp`.
    """
    # Força idioma para "pt" (whisper usa código ISO de 2 letras).
    _set_if_present(params, "language", _whisper_language_code(config.language))
    _set_if_present(params, "n_threads", config.threads)
    _set_if_present(params, "beam_size", config.beam_size)
    _set_if_present(params, "max_context", config.max_context)


def _set_if_present(obj: object, attr: str, value: object) -> None:
    """Define `attr` em `obj` apenas se o atributo existir (setattr defensivo)."""
    if hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception as exc:  # pragma: no cover - proteção defensiva
            logger.debug("Não foi possível definir whisper param %s: %s", attr, exc)


def _whisper_language_code(language: str) -> Literal["pt"] | str:
    """Converte o idioma da config (ex.: 'pt-BR') no código do whisper ('pt')."""
    return language.split("-")[0].lower() if language else "pt"
