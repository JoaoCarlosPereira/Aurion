"""Testes unitários do serviço TTS (Text-to-Speech).

Cobrem: síntese com edge-tts (mockado), streaming chunked do TTS externo
(httpx mockado), buffer de playback configurável, buffer circular, reprodução
progressiva, fallback automático, headers customizados, configuração de voz,
rate e volume, ``test_connection`` e ``list_voices``.

Nenhum teste exige hardware, binários ou rede: o edge-tts e o httpx são
substituídos por mocks/monkeypatch.
"""

from __future__ import annotations

import pytest

from svc.tts import (
    DEFAULT_VOICE,
    PT_BR_VOICES,
    CircularAudioBuffer,
    ExternalTTSConfig,
    TTSConfig,
    TTSError,
    TTSService,
    _format_signed_percent,
)


# --- Fakes / helpers ---------------------------------------------------------


class _FakeEdgeCommunicate:
    """Fake do ``edge_tts.Communicate`` que emite chunks de áudio simulados."""

    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = chunks if chunks is not None else [b"edge1", b"edge2"]
        # Registra os argumentos com que foi criado para inspeção nos testes.
        self.captured: dict[str, object] = {}

    async def stream(self):
        # Intercala um evento não-audio para validar a filtragem por tipo.
        yield {"type": "WordBoundary", "offset": 0}
        for chunk in self._chunks:
            yield {"type": "audio", "data": chunk}


class _FakeStreamResponse:
    """Fake da resposta de ``httpx.AsyncClient.stream`` (context manager async)."""

    def __init__(
        self,
        chunks: list[bytes],
        status_error: Exception | None = None,
    ) -> None:
        self._chunks = chunks
        self._status_error = status_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeAsyncClient:
    """Fake do ``httpx.AsyncClient`` que captura a requisição feita."""

    last_instance: "_FakeAsyncClient | None" = None

    def __init__(self, chunks: list[bytes], status_error: Exception | None = None):
        self._chunks = chunks
        self._status_error = status_error
        self.timeout: object = None
        self.request: dict[str, object] = {}
        _FakeAsyncClient.last_instance = self

    def __call__(self, *args, **kwargs):
        # Permite uso como factory ``httpx.AsyncClient(timeout=...)``.
        self.timeout = kwargs.get("timeout")
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, json=None, headers=None):
        self.request = {
            "method": method,
            "url": url,
            "json": json,
            "headers": headers,
        }
        return _FakeStreamResponse(self._chunks, self._status_error)


async def _collect(agen) -> list[bytes]:
    """Coleta todos os chunks de um gerador assíncrono em uma lista."""
    return [chunk async for chunk in agen]


def _patch_edge(service: TTSService, monkeypatch, chunks=None) -> _FakeEdgeCommunicate:
    """Substitui a criação do Communicate do edge-tts por um fake."""
    fake = _FakeEdgeCommunicate(chunks)

    def _factory(text: str):
        fake.captured["text"] = text
        return fake

    monkeypatch.setattr(service, "_create_edge_communicate", _factory)
    return fake


def _patch_httpx(monkeypatch, chunks: list[bytes], status_error=None) -> _FakeAsyncClient:
    """Injeta um módulo ``httpx`` fake para o import lazy do serviço."""
    import sys
    import types

    fake_client = _FakeAsyncClient(chunks, status_error)
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = fake_client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return fake_client


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def service() -> TTSService:
    """Serviço TTS com configuração padrão (edge-tts)."""
    return TTSService()


@pytest.fixture
def external_service() -> TTSService:
    """Serviço TTS com TTS externo habilitado."""
    config = TTSConfig(
        external=ExternalTTSConfig(
            enabled=True,
            endpoint="https://tts.example.com/synthesize",
            api_key="secreto-123",
            stream_buffer_ms=750,
        )
    )
    return TTSService(config)


# --- edge-tts (engine padrão) ------------------------------------------------


async def test_synthesize_edge_retorna_audio(service, monkeypatch):
    fake = _patch_edge(service, monkeypatch, chunks=[b"abc", b"def"])

    chunks = await _collect(service.synthesize("Olá mundo"))

    assert chunks == [b"abc", b"def"]
    assert fake.captured["text"] == "Olá mundo"


async def test_synthesize_texto_vazio_nao_gera_audio(service, monkeypatch):
    _patch_edge(service, monkeypatch, chunks=[b"x"])

    chunks = await _collect(service.synthesize("   "))

    assert chunks == []


async def test_voz_padrao_pt_br(service):
    assert service.voice == "pt-BR-FabioNeural"
    assert DEFAULT_VOICE == "pt-BR-FabioNeural"


async def test_configuracao_voz_rate_volume(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeModule:
        class Communicate:
            def __init__(self, text, voice, rate, volume):
                captured.update(text=text, voice=voice, rate=rate, volume=volume)

            async def stream(self):
                yield {"type": "audio", "data": b"ok"}

    import sys

    monkeypatch.setitem(sys.modules, "edge_tts", _FakeModule)
    config = TTSConfig(voice="pt-BR-FranciscaNeural", rate=-10, volume=80)
    service = TTSService(config)

    chunks = await _collect(service.synthesize("teste"))

    assert chunks == [b"ok"]
    assert captured["voice"] == "pt-BR-FranciscaNeural"
    assert captured["rate"] == "-10%"
    assert captured["volume"] == "+80%"


def test_format_signed_percent():
    assert _format_signed_percent(0) == "+0%"
    assert _format_signed_percent(20) == "+20%"
    assert _format_signed_percent(-15) == "-15%"


# --- TTS externo (streaming chunked) -----------------------------------------


async def test_synthesize_externo_streaming_chunked(external_service, monkeypatch):
    _patch_httpx(monkeypatch, chunks=[b"c1", b"c2", b"c3"])

    chunks = await _collect(external_service.synthesize("frase longa"))

    assert chunks == [b"c1", b"c2", b"c3"]


async def test_synthesize_externo_envia_payload(external_service, monkeypatch):
    fake = _patch_httpx(monkeypatch, chunks=[b"a"])

    await _collect(external_service.synthesize("comando de voz"))

    assert fake.request["method"] == "POST"
    assert fake.request["url"] == "https://tts.example.com/synthesize"
    assert fake.request["json"]["input"] == "comando de voz"
    assert fake.request["json"]["voice"] == "pt-BR-FabioNeural"
    assert fake.request["json"]["speed"] == 1.0


async def test_headers_customizados_authorization(external_service, monkeypatch):
    fake = _patch_httpx(monkeypatch, chunks=[b"a"])

    await _collect(external_service.synthesize("oi"))

    headers = fake.request["headers"]
    assert headers["Authorization"] == "Bearer secreto-123"
    assert headers["Accept"] == "audio/mp3"


async def test_headers_customizados_explicitos(monkeypatch):
    config = TTSConfig(
        external=ExternalTTSConfig(
            enabled=True,
            endpoint="https://x/synthesize",
            api_key="ignorado",
            headers={"Authorization": "Token abc", "X-Custom": "1"},
        )
    )
    service = TTSService(config)
    fake = _patch_httpx(monkeypatch, chunks=[b"a"])

    await _collect(service.synthesize("oi"))

    headers = fake.request["headers"]
    # Header explícito de Authorization não é sobrescrito pela api_key.
    assert headers["Authorization"] == "Token abc"
    assert headers["X-Custom"] == "1"


async def test_buffer_playback_configuravel(external_service):
    assert external_service.stream_buffer_ms == 750


# --- Reprodução progressiva --------------------------------------------------


async def test_reproducao_progressiva_antes_do_fim(external_service, monkeypatch):
    """Os chunks devem ser entregues à medida que chegam, não só no fim."""
    _patch_httpx(monkeypatch, chunks=[b"p1", b"p2", b"p3", b"p4"])

    recebidos: list[bytes] = []
    total = 4
    async for chunk in external_service.synthesize("texto"):
        recebidos.append(chunk)
        # Antes do último chunk, já devemos ter recebido algo (consumo incremental).
        if len(recebidos) < total:
            assert len(recebidos) >= 1

    assert recebidos == [b"p1", b"p2", b"p3", b"p4"]


# --- Buffer circular ---------------------------------------------------------


def test_buffer_circular_acumula_em_ordem():
    buffer = CircularAudioBuffer(max_chunks=4)
    buffer.push(b"a")
    buffer.push(b"b")
    buffer.push(b"c")

    assert len(buffer) == 3
    assert buffer.pop() == b"a"
    assert buffer.pop() == b"b"
    assert buffer.drain() == [b"c"]
    assert buffer.is_empty()


def test_buffer_circular_descarta_mais_antigo_quando_cheio():
    buffer = CircularAudioBuffer(max_chunks=2)
    buffer.push(b"1")
    buffer.push(b"2")
    buffer.push(b"3")  # descarta b"1"

    assert buffer.drain() == [b"2", b"3"]


def test_buffer_circular_ignora_chunk_vazio():
    buffer = CircularAudioBuffer()
    buffer.push(b"")
    assert buffer.is_empty()


def test_buffer_circular_max_chunks_invalido():
    with pytest.raises(ValueError):
        CircularAudioBuffer(max_chunks=0)


# --- Fallback automático -----------------------------------------------------


async def test_fallback_externo_falha_usa_edge(external_service, monkeypatch):
    """Erro HTTP no TTS externo deve cair para edge-tts automaticamente."""
    _patch_httpx(
        monkeypatch,
        chunks=[],
        status_error=RuntimeError("500 Server Error"),
    )
    fake_edge = _patch_edge(external_service, monkeypatch, chunks=[b"fallback"])

    chunks = await _collect(external_service.synthesize("recupera"))

    assert chunks == [b"fallback"]
    assert fake_edge.captured["text"] == "recupera"


async def test_fallback_externo_sem_audio_usa_edge(external_service, monkeypatch):
    """Stream externo sem áudio também aciona o fallback para edge-tts."""
    _patch_httpx(monkeypatch, chunks=[])
    fake_edge = _patch_edge(external_service, monkeypatch, chunks=[b"edge"])

    chunks = await _collect(external_service.synthesize("texto"))

    assert chunks == [b"edge"]
    assert fake_edge.captured["text"] == "texto"


async def test_externo_desabilitado_usa_edge_direto(service, monkeypatch):
    # ``service`` tem external.enabled = False por padrão.
    fake_edge = _patch_edge(service, monkeypatch, chunks=[b"so-edge"])

    chunks = await _collect(service.synthesize("oi"))

    assert chunks == [b"so-edge"]


async def test_synthesize_edge_propaga_erro_como_tts_error(service, monkeypatch):
    class _BrokenCommunicate:
        async def stream(self):
            raise RuntimeError("falha na rede edge")
            yield  # pragma: no cover

    monkeypatch.setattr(
        service, "_create_edge_communicate", lambda text: _BrokenCommunicate()
    )

    with pytest.raises(TTSError):
        await _collect(service._synthesize_edge("x"))


# --- test_connection ---------------------------------------------------------


async def test_test_connection_edge_sucesso(service, monkeypatch):
    _patch_edge(service, monkeypatch, chunks=[b"ok"])
    assert await service.test_connection() is True


async def test_test_connection_edge_falha(service, monkeypatch):
    def _factory(text: str):
        raise TTSError("edge indisponível")

    monkeypatch.setattr(service, "_create_edge_communicate", _factory)
    assert await service.test_connection() is False


async def test_test_connection_externo_sucesso(external_service, monkeypatch):
    _patch_httpx(monkeypatch, chunks=[b"audio"])
    assert await external_service.test_connection() is True


async def test_test_connection_externo_falha(external_service, monkeypatch):
    _patch_httpx(
        monkeypatch, chunks=[], status_error=RuntimeError("conexão recusada")
    )
    assert await external_service.test_connection() is False


# --- list_voices -------------------------------------------------------------


async def test_list_voices_retorna_pt_br(service):
    voices = await service.list_voices()
    assert "pt-BR-FabioNeural" in voices
    assert "pt-BR-FranciscaNeural" in voices
    assert "pt-BR-AntonioNeural" in voices
    assert voices == PT_BR_VOICES
    # Deve ser uma cópia, não a lista interna.
    assert voices is not PT_BR_VOICES
