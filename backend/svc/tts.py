"""Serviço de síntese de voz (Text-to-Speech) do Aurion.

Implementa o serviço TTS conforme a TechSpec (Seção 5.4) e a ADR-002, usando
``edge-tts`` como engine padrão e suportando, opcionalmente, um TTS externo via
HTTP com streaming chunked (``Transfer-Encoding: chunked``).

Princípios de projeto:

- **Streaming progressivo**: ``synthesize`` retorna um ``AsyncGenerator[bytes, None]``
  que entrega chunks de áudio assim que chegam, sem esperar o arquivo completo
  terminar (reprodução progressiva, reduzindo a latência percebida).
- **Fallback automático**: se o TTS externo estiver desabilitado, o endpoint
  retornar erro ou o streaming falhar, o serviço recorre automaticamente ao
  edge-tts (degradação graciosa, conforme TechSpec Seção 10).
- **Import lazy**: ``edge-tts`` e ``httpx`` são importados apenas quando
  necessários, permitindo que o módulo seja carregado em ambientes sem essas
  dependências (testes usam mocks/monkeypatch, sem hardware ou rede).

Observação: este serviço NÃO reproduz áudio em hardware; ele apenas gera/encaminha
os bytes de áudio. A reprodução (local ou via WebSocket) é responsabilidade de
outros serviços (ex.: ``listening.py``).
"""

from __future__ import annotations

import logging
from collections import deque
from typing import AsyncGenerator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Vozes PT-BR suportadas pelo edge-tts conforme TechSpec (Seção 5.4).
PT_BR_VOICES: list[str] = [
    "pt-BR-FabioNeural",
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
]

# Voz padrão (masculina brasileira mais natural), conforme TechSpec.
DEFAULT_VOICE = "pt-BR-FabioNeural"


# --- Modelos de configuração (Pydantic v2) -----------------------------------


class ExternalTTSConfig(BaseModel):
    """Configuração do TTS externo (opcional) com streaming chunked."""

    enabled: bool = False
    endpoint: str = "https://api.tts-provider.com/v1/synthesize"
    api_key: str = ""
    # Parâmetros enviados no corpo da requisição. ``input`` é preenchido em
    # tempo de execução com o texto a sintetizar; ``voice`` e ``speed`` vêm da
    # configuração.
    params: dict[str, object] = Field(
        default_factory=lambda: {"input": "", "voice": "", "speed": 1.0}
    )
    format: str = "mp3"
    timeout: int = 10
    # Tamanho do buffer de pré-carregamento (playback) em milissegundos.
    stream_buffer_ms: int = 500
    # Headers HTTP adicionais (ex.: {"Authorization": "Bearer <key>"}).
    headers: dict[str, str] = Field(default_factory=dict)


class TTSConfig(BaseModel):
    """Configuração do serviço TTS conforme a TechSpec (Seção 5.4)."""

    engine: str = "edge-tts"
    voice: str = DEFAULT_VOICE
    # Ajuste de velocidade (-100 a +100), aplicado ao edge-tts.
    rate: int = 0
    # Ajuste de volume (0 a 100), aplicado ao edge-tts.
    volume: int = 100
    external: ExternalTTSConfig = Field(default_factory=ExternalTTSConfig)


class TTSError(Exception):
    """Erro genérico do serviço TTS (ex.: ambas as engines indisponíveis)."""


def _format_signed_percent(value: int) -> str:
    """Formata um inteiro como percentual assinado exigido pelo edge-tts.

    O edge-tts espera strings como ``"+0%"``, ``"-10%"`` ou ``"+20%"`` para os
    parâmetros ``rate`` e ``volume``.
    """
    return f"+{value}%" if value >= 0 else f"{value}%"


class CircularAudioBuffer:
    """Buffer circular de chunks de áudio para reprodução progressiva.

    Acumula chunks recebidos do stream e os disponibiliza para consumo. O
    parâmetro ``max_chunks`` limita a quantidade de chunks retidos
    simultaneamente, evitando crescimento ilimitado de memória quando o produtor
    (stream HTTP) é mais rápido que o consumidor (reprodução).
    """

    def __init__(self, max_chunks: int = 64) -> None:
        if max_chunks <= 0:
            raise ValueError("max_chunks deve ser positivo")
        self._buffer: deque[bytes] = deque(maxlen=max_chunks)
        self._max_chunks = max_chunks

    @property
    def max_chunks(self) -> int:
        return self._max_chunks

    def __len__(self) -> int:
        return len(self._buffer)

    def is_empty(self) -> bool:
        return len(self._buffer) == 0

    def push(self, chunk: bytes) -> None:
        """Adiciona um chunk ao buffer (descarta o mais antigo se cheio)."""
        if chunk:
            self._buffer.append(chunk)

    def pop(self) -> bytes | None:
        """Remove e retorna o chunk mais antigo, ou ``None`` se vazio."""
        if self._buffer:
            return self._buffer.popleft()
        return None

    def drain(self) -> list[bytes]:
        """Esvazia o buffer retornando todos os chunks na ordem de chegada."""
        chunks = list(self._buffer)
        self._buffer.clear()
        return chunks


class TTSService:
    """Serviço de síntese de voz com edge-tts e TTS externo em streaming.

    Expõe ``synthesize`` como um gerador assíncrono de chunks de áudio
    (``AsyncGenerator[bytes, None]``), permitindo reprodução progressiva.
    """

    def __init__(self, config: TTSConfig | None = None) -> None:
        self._config = config or TTSConfig()

    @property
    def config(self) -> TTSConfig:
        return self._config

    @property
    def voice(self) -> str:
        return self._config.voice

    @property
    def stream_buffer_ms(self) -> int:
        """Tamanho configurável do buffer de playback (em milissegundos)."""
        return self._config.external.stream_buffer_ms

    # --- API pública ---------------------------------------------------------

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Sintetiza ``text`` e gera chunks de áudio progressivamente.

        Se o TTS externo estiver habilitado, tenta usá-lo via streaming chunked.
        Em caso de falha (ou se desabilitado), recorre automaticamente ao
        edge-tts. Levanta ``TTSError`` somente se ambas as engines falharem.
        """
        text = (text or "").strip()
        if not text:
            # Sem texto não há áudio a gerar; encerra o gerador imediatamente.
            return

        external = self._config.external
        if external.enabled:
            try:
                produced = False
                async for chunk in self._synthesize_external(text):
                    produced = True
                    yield chunk
                if produced:
                    return
                # Stream externo não produziu áudio: cai para o fallback.
                logger.warning(
                    "TTS externo não retornou áudio; usando edge-tts (fallback)."
                )
            except Exception as exc:  # noqa: BLE001 - degradação graciosa
                logger.warning(
                    "Falha no TTS externo (%s); usando edge-tts (fallback).", exc
                )

        async for chunk in self._synthesize_edge(text):
            yield chunk

    async def test_connection(self) -> bool:
        """Testa a engine TTS ativa, retornando ``True`` em caso de sucesso.

        Se o TTS externo estiver habilitado, testa o endpoint externo; caso
        contrário (ou se ele falhar), valida que o edge-tts produz áudio.
        """
        if self._config.external.enabled:
            try:
                async for _chunk in self._synthesize_external("teste"):
                    return True
            except Exception as exc:  # noqa: BLE001 - degradação graciosa
                logger.warning("Teste do TTS externo falhou: %s", exc)
                return False
            # Não produziu chunks, mas também não falhou: considera indisponível.
            return False

        try:
            async for _chunk in self._synthesize_edge("teste"):
                return True
        except Exception as exc:  # noqa: BLE001 - degradação graciosa
            logger.warning("Teste do edge-tts falhou: %s", exc)
            return False
        return False

    async def list_voices(self) -> list[str]:
        """Lista as vozes PT-BR disponíveis para o edge-tts."""
        return list(PT_BR_VOICES)

    # --- Engines internas ----------------------------------------------------

    async def _synthesize_edge(self, text: str) -> AsyncGenerator[bytes, None]:
        """Gera áudio com o edge-tts (engine padrão), em chunks progressivos.

        O ``edge_tts`` é importado de forma lazy para que o módulo possa ser
        carregado em ambientes sem a dependência (testes mockam ``_create_edge_communicate``).
        """
        communicate = self._create_edge_communicate(text)
        try:
            # ``edge_tts.Communicate.stream`` é um gerador assíncrono que emite
            # eventos. Os de tipo "audio" carregam os bytes em ``data``.
            async for message in communicate.stream():
                if message.get("type") == "audio" and message.get("data"):
                    yield message["data"]
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"Falha ao sintetizar com edge-tts: {exc}") from exc

    def _create_edge_communicate(self, text: str):
        """Cria o objeto ``Communicate`` do edge-tts (ponto de mock nos testes).

        Import lazy de ``edge_tts``; levanta ``TTSError`` se indisponível.
        """
        try:
            import edge_tts  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercido via mock
            raise TTSError(
                "edge-tts não está instalado; não é possível sintetizar voz."
            ) from exc

        return edge_tts.Communicate(
            text,
            voice=self._config.voice,
            rate=_format_signed_percent(self._config.rate),
            volume=_format_signed_percent(self._config.volume),
        )

    async def _synthesize_external(self, text: str) -> AsyncGenerator[bytes, None]:
        """Consome o TTS externo via HTTP com streaming chunked progressivo.

        Faz POST ao endpoint configurado e itera sobre os bytes do corpo da
        resposta (``Transfer-Encoding: chunked``), acumulando-os em um buffer
        circular e os entregando assim que disponíveis — sem esperar o stream
        terminar. ``httpx`` é importado de forma lazy.
        """
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercido via mock
            raise TTSError("httpx não está instalado; TTS externo indisponível.") from exc

        external = self._config.external
        payload = dict(external.params)
        payload["input"] = text
        # Garante voz/velocidade coerentes com a configuração quando não definidos.
        if not payload.get("voice"):
            payload["voice"] = self._config.voice
        if "speed" not in payload:
            payload["speed"] = 1.0

        headers = dict(external.headers)
        if external.api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {external.api_key}"
        headers.setdefault("Accept", f"audio/{external.format}")

        buffer = CircularAudioBuffer()
        timeout = external.timeout

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", external.endpoint, json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                # Itera os chunks conforme chegam (reprodução progressiva).
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    buffer.push(chunk)
                    # Drena o buffer entregando os chunks acumulados em ordem.
                    next_chunk = buffer.pop()
                    while next_chunk is not None:
                        yield next_chunk
                        next_chunk = buffer.pop()

        # Garante a entrega de qualquer chunk remanescente no buffer.
        for remaining in buffer.drain():
            yield remaining
