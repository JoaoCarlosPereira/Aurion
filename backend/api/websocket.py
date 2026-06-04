"""Endpoints WebSocket para o Aurion (TechSpec Seção 3.2).

Expõe três endpoints:

- ``WS /ws/status`` — broadcast de estado do sistema (idle/listening/detecting/…​).
  Clientes assinam recebendo atualizações quando o Listening Service troca de estado.

- ``WS /ws/audio/{session_id}`` — streaming de áudio TTS do servidor para o cliente.
  Chunks de áudio (bytes) são enviados progressivamente conforme o TTS sintetiza.

- ``WS /ws/voice-command/{session_id}`` — comando de voz do cliente para o servidor.
  O cliente envia ``audio_start``, chunks ``audio_chunk`` e ``audio_end``; o servidor
  encaminha ao pipeline STT -> Hermes -> TTS e devolve o resultado (texto + áudio).

O ``on_state`` callback do ``ListeningService`` conecta-se ao status WS.
O ``on_audio`` callback conecta-se ao audio WS.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from collections import defaultdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from config.settings import ConfigManager, get_config_manager
from svc.listening import StateCallback

logger = logging.getLogger(__name__)

# Tempo máximo (s) que um WebSocket de audio fica aberto sem envio de dados.
AUDIO_HEARTBEAT_TIMEOUT = 30.0

# Tipo de mensagem WebSocket (cliente -> servidor).
WsMessageType = Literal[
    "audio_start",
    "audio_chunk",
    "audio_end",
    "subscribe_status",
]

# Tipo de mensagem WebSocket (servidor -> cliente).
ServerMessageType = Literal[
    "state_update",
    "audio_data",
    "tts_result",
    "error",
    "status",
]


router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Gerenciador de conexoes WebSocket
# ---------------------------------------------------------------------------


class WebSocketManager:
    """Gerencia conexoes WebSocket ativas e broadcast.

    Mantem dois conjuntos de conexoes:
    - ``status_clients``: assinantes do endpoint /ws/status.
    - ``audio_clients``: sessoes de audio /ws/audio/{session_id}.
    - ``voice_clients``: sessoes de comando de voz /ws/voice-command/{session_id}.

    O broadcast de estado e' thread-safe: callbacks vinhos da thread do
    Listening Service usam uma fila sincronizada que e' drenada na proxima
    oportunidade do event loop (``call_soon_threadsafe``).
    """

    def __init__(self) -> None:
        self._status_clients: set[WebSocket] = set()
        self._audio_clients: dict[str, WebSocket] = {}
        self._voice_clients: dict[str, WebSocket] = {}
        # Fila thread-safe para mensagens vindas de threads externas.
        self._pending_messages: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._loop_scheduled = False
        self._lock = threading.Lock()

    # --- Status -------------------------------------------------------------

    def add_status_client(self, ws: WebSocket) -> None:
        self._status_clients.add(ws)

    def remove_status_client(self, ws: WebSocket) -> None:
        self._status_clients.discard(ws)

    async def broadcast_state(self, state: str, message: str | None = None) -> None:
        """Envia update de estado para todos os clientes de status."""
        payload = {"type": "state_update", "state": state, "message": message}
        dead: set[WebSocket] = set()
        for client in self._status_clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.add(client)
        self._status_clients -= dead

    def on_state_from_thread(self, state: str, message: str | None) -> None:
        """Thread-safe: chamado da thread do Listening Service.
        Agenda o broadcast no event loop usando call_soon_threadsafe."""
        self._pending_messages.put((state, message))
        loop = asyncio.get_event_loop()
        if not self._loop_scheduled:
            self._loop_scheduled = True
            try:
                loop.call_soon_threadsafe(self._drain_messages)
            except RuntimeError:
                # Event loop fechado — ignora.
                pass

    def _drain_messages(self) -> None:
        """Drena a fila de mensagens e as enfileira no event loop."""
        with self._lock:
            self._loop_scheduled = False
        messages: list[tuple[str, str | None]] = []
        while not self._pending_messages.empty():
            try:
                messages.append(self._pending_messages.get_nowait())
            except queue.Empty:
                break
        if messages:
            asyncio.get_event_loop().create_task(self._broadcast_queued(messages))

    async def _broadcast_queued(
        self, messages: list[tuple[str, str | None]]
    ) -> None:
        for state, message in messages:
            await self.broadcast_state(state, message)

    # --- Audio --------------------------------------------------------------

    def add_audio_client(self, session_id: str, ws: WebSocket) -> None:
        self._audio_clients[session_id] = ws

    def remove_audio_client(self, session_id: str) -> None:
        self._audio_clients.pop(session_id, None)

    async def send_audio_chunk(self, session_id: str, chunk: bytes) -> None:
        """Envia um chunk de audio para uma sessao de audio."""
        client = self._audio_clients.get(session_id)
        if client is not None:
            try:
                await client.send_bytes(chunk)
            except Exception:
                self.remove_audio_client(session_id)

    # --- Voice Command ------------------------------------------------------

    def add_voice_client(self, session_id: str, ws: WebSocket) -> None:
        self._voice_clients[session_id] = ws

    def remove_voice_client(self, session_id: str) -> None:
        self._voice_clients.pop(session_id, None)

    # --- Utilidades ---------------------------------------------------------

    @property
    def status_count(self) -> int:
        return len(self._status_clients)

    @property
    def audio_count(self) -> int:
        return len(self._audio_clients)

    @property
    def voice_count(self) -> int:
        return len(self._voice_clients)


# Singleton gerenciado pelo lifespan.
_ws_manager: WebSocketManager | None = None


def get_ws_manager() -> WebSocketManager:
    if _ws_manager is None:
        raise RuntimeError("WebSocket manager nao inicializado. Inicie via lifespan.")
    return _ws_manager


def set_ws_manager(manager: WebSocketManager) -> None:
    global _ws_manager
    _ws_manager = manager


# ---------------------------------------------------------------------------
# Callbacks para o Listening Service
# ---------------------------------------------------------------------------


def _on_state_callback(manager: WebSocketManager) -> StateCallback:
    """Retorna um callback para conectar o Listening Service ao WS status."""

    def callback(state: str, message: str | None) -> None:
        asyncio.create_task(manager.broadcast_state(state, message))

    return callback


# ---------------------------------------------------------------------------
# Endpoints WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/status")
async def ws_status(
    websocket: WebSocket,
    manager: WebSocketManager = Depends(get_ws_manager),
) -> None:
    """Endpoint de status em tempo real.

    O cliente se conecta e recebe atualizacoes automaticas quando o
    Listening Service muda de estado (idle, listening, detecting, stt,
    processing, tts, error).
    """
    await websocket.accept()
    manager.add_status_client(websocket)
    # Envia o estado atual imediatamente.
    try:
        await websocket.send_json({
            "type": "status",
            "state": "connected",
            "clients": manager.status_count,
        })
        while True:
            # Aguarda mensagens do cliente (ex.: ping).
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.remove_status_client(websocket)
    except Exception as exc:
        logger.error("Erro no WebSocket /ws/status: %s", exc)
        manager.remove_status_client(websocket)


@router.websocket("/ws/audio/{session_id}")
async def ws_audio(
    websocket: WebSocket,
    session_id: str,
    manager: WebSocketManager = Depends(get_ws_manager),
) -> None:
    """Streaming de audio TTS do servidor para o cliente.

    O servidor envia chunks de audio (bytes) progressivamente conforme
    o TTS sintetiza a resposta. O cliente pode enviar "ping" para
    manter a conexao ativa.
    """
    await websocket.accept()
    manager.add_audio_client(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                continue
            # O cliente pode enviar "stop" para encerrar.
            if data == "stop":
                break
    except WebSocketDisconnect:
        manager.remove_audio_client(session_id)
    except Exception as exc:
        logger.error("Erro no WebSocket /ws/audio/%s: %s", session_id, exc)
        manager.remove_audio_client(session_id)


@router.websocket("/ws/voice-command/{session_id}")
async def ws_voice_command(
    websocket: WebSocket,
    session_id: str,
    manager: WebSocketManager = Depends(get_ws_manager),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> None:
    """Comando de voz: cliente envia audio, recebe texto e audio de volta.

    Protocolo cliente -> servidor:
    1. ``{"type": "audio_start", "format": "pcm", "sample_rate": 16000}``
    2. Mensagens ``{"type": "audio_chunk", "data": "base64..."}``
    3. ``{"type": "audio_end"}``

    Protocolo servidor -> cliente:
    1. ``{"type": "tts_result", "text": "...", "session_id": "..."}``
    2. Chunks de audio via ``send_bytes()``
    3. ``{"type": "error", "message": "..."}``
    """
    await websocket.accept()
    manager.add_voice_client(session_id, websocket)

    try:
        audio_chunks: list[bytes] = []
        expecting_start = True

        while True:
            raw = await websocket.receive_text()

            try:
                msg: dict[str, Any] = __import__("json").loads(raw)
            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "message": "Mensagem JSON invalida.",
                })
                continue

            msg_type: WsMessageType = msg.get("type", "")  # type: ignore[assignment]

            if expecting_start and msg_type == "audio_start":
                expecting_start = False
                audio_chunks = []
                continue

            if msg_type == "audio_chunk":
                import base64

                try:
                    b64 = msg.get("data", "")
                    chunk = base64.b64decode(b64)
                    audio_chunks.append(chunk)
                except Exception:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Falha ao decodificar chunk de audio.",
                    })
                continue

            if msg_type == "audio_end":
                break

    except WebSocketDisconnect:
        manager.remove_voice_client(session_id)
        return
    except Exception as exc:
        logger.error("Erro no WebSocket /ws/voice-command/%s: %s", session_id, exc)
        manager.remove_voice_client(session_id)
        return

    # Processa o audio capturado.
    if not audio_chunks:
        await websocket.send_json({
            "type": "error",
            "message": "Nenhum audio recebido.",
        })
        return

    # Combina os chunks.
    import base64

    audio_bytes = b"".join(audio_chunks)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    # Envia o resultado de volta (simplificado: apenas texto via STT mock).
    # Em implementacao completa, encaminha ao Listening Service pipeline.
    await websocket.send_json({
        "type": "tts_result",
        "text": f"Audio recebido ({len(audio_bytes)} bytes).",
        "session_id": session_id,
    })

    manager.remove_voice_client(session_id)
