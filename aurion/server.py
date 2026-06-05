"""FastAPI server — API endpoints e static files do Aurion."""

import asyncio
import logging
import os
import queue
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aurion.database import (
    DEFAULT_DB_PATH,
    create_conversation,
    end_conversation,
    get_conversation,
    get_setting,
    init_db,
    insert_command,
    insert_log,
    list_commands,
    list_conversations,
    list_logs,
    set_setting,
)
from aurion.audio_devices import (
    get_mic_index,
    get_microphones,
    get_speaker_index,
    get_speakers,
    refresh_devices,
    resolve_mic_index,
    resolve_speaker_index,
    set_mic_index,
    set_speaker_index,
    set_system_volume_max,
)
from aurion.discovery import ServiceDiscovery
from aurion.greeting import play_greeting
from aurion.instance_lock import acquire_instance_lock
from aurion.hermes import HermesClient, HermesError, VoiceConversationContext
from aurion.listener import VoiceListener, parse_queue_item
from aurion.tts import TTSService
from aurion.transcriptions import list_transcriptions

logger = logging.getLogger("aurion.api")
load_dotenv()

# Configure logging for aurion logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

# ── Global state ─────────────────────────────────────────────────

_db_path: str = DEFAULT_DB_PATH
_command_queue: queue.Queue = queue.Queue()
_hermes_client: HermesClient | None = None
_tts_service: TTSService | None = None
_discovery: ServiceDiscovery | None = None
_listener: VoiceListener | None = None
_voice_context: VoiceConversationContext | None = None
_start_time: float = time.time()
_command_worker_task: asyncio.Task | None = None
_instance_lock = None

# ── Pydantic models ──────────────────────────────────────────────

class CommandRequest(BaseModel):
    input_text: str
    source: Literal["web"] = "web"


class CommandResponse(BaseModel):
    status: str
    response: str
    source: str
    timestamp: datetime


class StatusResponse(BaseModel):
    listening: bool
    in_conversation: bool = False
    hermes_connected: bool
    tts_available: bool
    uptime_seconds: float
    services: dict[str, str] = {}
    health: dict[str, bool] = {}


class LogResponse(BaseModel):
    level: str
    component: str
    message: str
    timestamp: str


class TranscriptionInfo(BaseModel):
    id: int
    timestamp: str
    transcript: str
    mode: str
    confidence: float | None = None


class VoiceInfo(BaseModel):
    id: str
    name: str
    lang: str


class VoiceTestRequest(BaseModel):
    voice_id: str
    text: str


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


# ── Helpers ──────────────────────────────────────────────────────

def _find_free_port(start: int = 8080, max_attempts: int = 10) -> int:
    """Encontra porta livre começando de *start*."""
    import socket
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start


def _resolve_conversation_id(source: str, voice_mode: bool) -> int:
    """Retorna o id da conversa ativa ou cria uma conversa de turno único."""
    if voice_mode and _voice_context and _voice_context.active and _voice_context.conversation_id:
        return _voice_context.conversation_id
    conv_id = create_conversation(_db_path, source)
    end_conversation(_db_path, conv_id)
    return conv_id


async def _command_worker():
    """Worker em background que consome a fila de comandos de voz."""
    global _hermes_client, _tts_service
    logger.info("Voice command worker iniciado")

    while True:
        try:
            item = await asyncio.to_thread(_command_queue.get, timeout=1)
            command, wait_response, voice_mode = parse_queue_item(item)
            logger.info(
                "Worker: comando '%s' (aguardar=%s, voz=%s)",
                command,
                wait_response,
                voice_mode,
            )

            try:
                history = None
                if voice_mode and _voice_context and _voice_context.active:
                    history = _voice_context.snapshot()

                result = await _hermes_client.send_command(  # type: ignore[union-attr]
                    command, voice_mode=voice_mode, history=history
                )
                insert_command(
                    _db_path, source="voice", input_text=command,
                    response_text=result["response"], hermes_status=result["status"],
                    conversation_id=_resolve_conversation_id("voice", voice_mode),
                )
                insert_log(_db_path, "INFO", "voice",
                           f"Comando: {command} → {result['response'][:60]}")

                if voice_mode and _voice_context and _voice_context.active:
                    _voice_context.append_turn(command, result["response"])

                if _listener and voice_mode:
                    _listener.set_last_response(result["response"])  # noqa: SLF001

                if _tts_service:
                    if wait_response:
                        try:
                            await asyncio.to_thread(
                                _tts_service.speak_blocking, result["response"]
                            )
                            logger.info(
                                "TTS concluído (conversa): %s",
                                result["response"][:40],
                            )
                        finally:
                            if _listener:
                                _listener.notify_response_done()  # noqa: SLF001
                    else:
                        t = threading.Thread(
                            target=_tts_service.speak,
                            args=(result["response"],),
                            daemon=True,
                        )
                        t.start()
                        logger.info("TTS agendado (voice): %s", result["response"][:40])

            except HermesError as exc:
                insert_command(
                    _db_path, source="voice", input_text=command,
                    response_text=str(exc), hermes_status="error",
                    conversation_id=_resolve_conversation_id("voice", voice_mode),
                )
                insert_log(_db_path, "ERROR", "voice", f"Hermes error: {exc}")
                logger.error("Hermes error no comando '%s': %s", command, exc)
                if wait_response and _listener:
                    _listener.notify_response_done()  # noqa: SLF001
            except Exception as exc:
                logger.error("Erro processando comando de voz '%s': %s", command, exc)
                if wait_response and _listener:
                    _listener.notify_response_done()  # noqa: SLF001

        except queue.Empty:
            continue
        except Exception as exc:
            logger.error("Erro no command worker: %s", exc)


def _init_components():
    """Inicializa todos os módulos do Aurion."""
    global _hermes_client, _tts_service, _discovery, _listener, _voice_context, _db_path, _start_time

    _start_time = time.time()
    _db_path = os.getenv("AURION_DB", DEFAULT_DB_PATH)
    init_db(_db_path)
    insert_log(_db_path, "INFO", "api", "Inicializando componentes do Aurion")

    # Carregar e validar configurações de áudio
    refresh_devices()
    for key, set_func, resolve_func in [
        ("microphone_index", set_mic_index, resolve_mic_index),
        ("speaker_index", set_speaker_index, resolve_speaker_index),
    ]:
        val = get_setting(_db_path, key)
        preferred = int(val) if val is not None and str(val).isdigit() else None
        resolved = resolve_func(preferred)
        if resolved is not None:
            set_func(resolved)
            if str(resolved) != str(preferred):
                set_setting(_db_path, key, str(resolved))
            insert_log(_db_path, "INFO", "audio", f"{key}={resolved}")

    set_system_volume_max()
    insert_log(_db_path, "INFO", "audio", "Volume ALSA no máximo")

    _hermes_client = HermesClient(
        api_url=os.getenv("HERMES_API_URL"),
        api_key=os.getenv("HERMES_API_KEY"),
        model=os.getenv("HERMES_MODEL"),
    )
    _tts_service = TTSService()

    # Discovery
    _discovery = ServiceDiscovery()
    discovered = _discovery.discover(timeout=3.0)
    health = _discovery.health_check(discovered)
    insert_log(_db_path, "INFO", "discovery",
               f"Serviços descobertos: {list(discovered.keys())}")

    # VoiceListener (início adiado no lifespan para não captar a saudação inicial)
    trigger_word = os.getenv("TRIGGER_WORD", "ermes")
    _voice_context = VoiceConversationContext(
        on_start=lambda: create_conversation(_db_path, "voice"),
        on_end=lambda conv_id: end_conversation(_db_path, conv_id),
    )
    _listener = VoiceListener(
        _command_queue,
        trigger_word=trigger_word,
        db_path=_db_path,
        conversation_context=_voice_context,
    )
    insert_log(_db_path, "INFO", "listener", f"Escuta configurada (trigger='{trigger_word}')")

    return discovered, health


# ── App ──────────────────────────────────────────────────────────

def _start_listener_delayed(delay_seconds: float = 5.0) -> None:
    """Inicia escuta após a saudação inicial para evitar falso positivo no microfone."""
    time.sleep(delay_seconds)
    if _listener:
        _listener.start()
        insert_log(_db_path, "INFO", "listener", "Escuta de voz iniciada após saudação")
        logger.info("VoiceListener iniciado após %.0fs de atraso", delay_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _instance_lock
    logger.info("Lifespan: adquirindo lock...")
    _instance_lock = acquire_instance_lock()
    if _instance_lock is None:
        logger.error(
            "Outra instância do Aurion já está em execução. "
            "Encerre o processo anterior ou remova %s",
            os.getenv("AURION_LOCK_FILE", "/tmp/aurion.lock"),
        )
        sys.exit(1)
    logger.info("Lifespan: lock adquirido, inicializando componentes...")

    discovered, health = _init_components()
    logger.info("Lifespan: componentes inicializados, reproduzindo saudação...")
    play_greeting(blocking=True)
    insert_log(_db_path, "INFO", "greeting", "Saudação inicial reproduzida")
    logger.info("Lifespan: iniciando listener em thread...")
    threading.Thread(target=_start_listener_delayed, daemon=True, name="aurion-listener-delay", kwargs={"delay_seconds": 1.0}).start()

    # Iniciar worker de comandos de voz
    logger.info("Lifespan: criando task do command worker...")
    global _command_worker_task
    _command_worker_task = asyncio.create_task(_command_worker())
    logger.info("Lifespan: inserindo log do worker...")
    insert_log(_db_path, "INFO", "api", "Worker de comandos de voz iniciado")
    logger.info("Lifespan: sobre o yield — servidor vai iniciar!")

    yield

    logger.info("Lifespan: shutdown...")
    # Shutdown
    if _command_worker_task:
        _command_worker_task.cancel()
    if _listener:
        _listener.stop()
    if _instance_lock:
        _instance_lock.release()
        _instance_lock = None
    insert_log(_db_path, "INFO", "api", "Servidor Aurion parado")
    logger.info("Lifespan: shutdown concluído")


app = FastAPI(title="Aurion", lifespan=lifespan)


# ── API Endpoints ────────────────────────────────────────────────

@app.post("/api/command", response_model=CommandResponse)
async def execute_command(req: CommandRequest):
    """Envia comando ao Hermes Agent e retorna resposta."""
    try:
        result = await _hermes_client.send_command(req.input_text)  # type: ignore[union-attr]
        conv_id = _resolve_conversation_id(req.source, voice_mode=False)
        cmd_id = insert_command(
            _db_path, source=req.source, input_text=req.input_text,
            response_text=result["response"], hermes_status=result["status"],
            conversation_id=conv_id,
        )
        insert_log(_db_path, "INFO", "api", f"Comando executado → ID {cmd_id}")
        # TTS em background (não bloqueia a resposta HTTP)
        t = threading.Thread(
            target=_tts_service.speak, args=(result["response"],), daemon=True
        )
        t.start()
        logger.info("TTS agendado: %s", result["response"][:40])
        return CommandResponse(
            status=result["status"], response=result["response"],
            source=req.source, timestamp=datetime.now(),
        )
    except HermesError as exc:
        conv_id = _resolve_conversation_id(req.source, voice_mode=False)
        insert_command(
            _db_path, source=req.source, input_text=req.input_text,
            response_text=str(exc), hermes_status="error",
            conversation_id=conv_id,
        )
        raise HTTPException(status_code=502, detail="Hermes unavailable")


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str
    status: str | None = None


class ConversationResponse(BaseModel):
    id: int
    started_at: str
    ended_at: str | None
    source: str
    turn_count: int
    messages: list[ConversationMessage]


@app.get("/api/conversations", response_model=list[ConversationResponse])
async def get_conversations(
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
):
    """Lista conversas completas com mensagens do usuário e do Aurion."""
    return list_conversations(
        _db_path, source=source, date_from=date_from, date_to=date_to, limit=limit
    )


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_detail(conversation_id: int):
    """Detalhe de uma conversa específica."""
    conv = get_conversation(_db_path, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.get("/api/history")
async def get_history(
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
):
    """Lista comandos com filtros opcionais."""
    cmds = list_commands(_db_path, source=source, date_from=date_from,
                         date_to=date_to, limit=limit)
    for c in cmds:
        c["timestamp"] = str(c["timestamp"])
    return cmds


@app.get("/api/history/{cmd_id}")
async def get_history_detail(cmd_id: int):
    """Detalhe de um comando específico."""
    cmd = list_commands(_db_path)
    for c in cmd:
        if str(c.get("id", "")) == str(cmd_id):
            c["timestamp"] = str(c["timestamp"])
            return c
    raise HTTPException(status_code=404, detail="Command not found")


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Status do servidor e serviços."""
    if _listener:
        _listener.ensure_running()  # noqa: SLF001
    thread_alive = (
        _listener is not None
        and _listener._thread is not None
        and _listener._thread.is_alive()
    )
    status = {
        "listening": _listener is not None and _listener._running and thread_alive,  # noqa: SLF001
        "in_conversation": _listener.in_conversation if _listener else False,  # noqa: SLF001
        "hermes_connected": True,
        "tts_available": _tts_service is not None,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "services": _discovery.services if _discovery else {},
        "health": _discovery.health_check() if _discovery else {},
    }
    return StatusResponse(**status)


@app.get("/api/logs")
async def get_logs(
    level: str | None = None,
    component: str | None = None,
    limit: int = 200,
):
    """Logs com filtro por nível/componente."""
    logs = list_logs(_db_path, level=level, component=component, limit=limit)
    for l in logs:
        l["timestamp"] = str(l["timestamp"])
    return logs


@app.get("/api/voices")
async def list_voices():
    """Lista vozes disponíveis."""
    voices = _tts_service.list_voices()  # type: ignore[union-attr]
    return [VoiceInfo(**v) for v in voices]


@app.put("/api/voices/{voice_id}")
async def set_voice(voice_id: str):
    """Configura voz padrão."""
    _tts_service.set_voice(voice_id)  # type: ignore[union-attr]
    set_setting(_db_path, "voice_id", voice_id)
    return {"status": "ok", "voice_id": voice_id}


@app.post("/api/voices/test")
async def test_voice(req: VoiceTestRequest):
    """Testa amostra de áudio com voz específica."""
    _tts_service.test_voice(req.voice_id, req.text)  # type: ignore[union-attr]
    return {"status": "ok", "message": "Audio sample sent"}


@app.get("/api/config")
async def get_config():
    """Retorna configurações atuais."""
    config = {
        "trigger_word": os.getenv("TRIGGER_WORD", "ermes"),
        "hermes_url": _hermes_client.api_url if _hermes_client else None,  # type: ignore[union-attr]
        "port": _find_free_port(),
    }
    return config


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    """Atualiza configurações."""
    set_setting(_db_path, req.key, req.value)
    if req.key == "trigger_word":
        # Update listener trigger word
        if _listener:
            _listener.trigger_word = req.value
    return {"status": "ok", "key": req.key, "value": req.value}


@app.post("/api/listen/start")
async def start_listening():
    """Inicia escuta de voz."""
    if _listener and _listener._running:  # noqa: SLF001
        return {"status": "ok", "message": "Listening already active"}
    if _listener:
        _listener.start()
    insert_log(_db_path, "INFO", "listener", "Escuta iniciada via API")
    return {"status": "ok", "message": "Listening started"}


@app.post("/api/listen/stop")
async def stop_listening():
    """Para escuta de voz."""
    if _listener:
        _listener.stop()
    insert_log(_db_path, "INFO", "listener", "Escuta parada via API")
    return {"status": "ok", "message": "Listening stopped"}


@app.post("/api/listen/restart")
async def restart_listening():
    """Reinicia escuta de voz (libera microfone ALSA e reconfigura dispositivo)."""
    if _listener:
        _listener.restart()
    insert_log(_db_path, "INFO", "listener", "Escuta reiniciada via API")
    return {"status": "ok", "message": "Listening restarted"}


@app.get("/api/config/port")
async def get_port():
    """Retorna a porta atual do servidor."""
    return {"port": _find_free_port()}


@app.get("/api/transcriptions")
async def get_transcriptions(
    mode: str | None = None,
    limit: int = 200,
):
    """Lista todas as transcrições de áudio (wake word, comandos, desconhecidos)."""
    txs = list_transcriptions(_db_path, mode=mode, limit=limit)
    for t in txs:
        t["timestamp"] = str(t["timestamp"])
    return txs


# ── Audio Devices ────────────────────────────────────────────────

class AudioDevice(BaseModel):
    index: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


class AudioDevicesResponse(BaseModel):
    microphones: list[AudioDevice]
    speakers: list[AudioDevice]
    selected_microphone_index: int | None = None
    selected_speaker_index: int | None = None


class AudioDeviceConfig(BaseModel):
    device_type: str  # "microphone" or "speaker"
    device_index: int


@app.get("/api/audio/devices", response_model=AudioDevicesResponse)
async def get_audio_devices():
    """Lista todos os microfones e alto-falantes detectados."""
    devices = refresh_devices()
    return AudioDevicesResponse(
        microphones=[AudioDevice(**d) for d in devices["microphones"]],
        speakers=[AudioDevice(**d) for d in devices["speakers"]],
        selected_microphone_index=get_mic_index(),
        selected_speaker_index=get_speaker_index(),
    )


@app.get("/api/audio/microphones")
async def get_audio_microphones():
    """Lista apenas os microfones detectados."""
    mics = get_microphones()
    if not mics:
        devices = refresh_devices()
        mics = devices["microphones"]
    return [AudioDevice(**m) for m in mics]


@app.get("/api/audio/speakers")
async def get_audio_speakers():
    """Lista apenas os alto-falantes detectados."""
    spk = get_speakers()
    if not spk:
        devices = refresh_devices()
        spk = devices["speakers"]
    return [AudioDevice(**s) for s in spk]


@app.post("/api/audio/microphone")
async def set_microphone(config: AudioDeviceConfig):
    """Configura o microfone padrão."""
    if config.device_type != "microphone":
        raise HTTPException(status_code=400, detail="device_type must be 'microphone'")
    resolved = resolve_mic_index(config.device_index)
    if resolved is None:
        raise HTTPException(status_code=400, detail="Nenhum microfone disponível")
    set_mic_index(resolved)
    set_setting(_db_path, "microphone_index", str(resolved))
    if _listener:
        _listener.restart()
    insert_log(_db_path, "INFO", "audio", f"Microfone alterado para índice {resolved}")
    return {"status": "ok", "device_type": "microphone", "device_index": resolved}


@app.post("/api/audio/speaker")
async def set_speaker(config: AudioDeviceConfig):
    """Configura o alto-falante padrão."""
    if config.device_type != "speaker":
        raise HTTPException(status_code=400, detail="device_type must be 'speaker'")
    resolved = resolve_speaker_index(config.device_index)
    if resolved is None:
        raise HTTPException(status_code=400, detail="Nenhum alto-falante disponível")
    set_speaker_index(resolved)
    set_setting(_db_path, "speaker_index", str(resolved))
    insert_log(_db_path, "INFO", "audio", f"Alto-falante alterado para índice {resolved}")
    return {"status": "ok", "device_type": "speaker", "device_index": resolved}


# ── Static files ─────────────────────────────────────────────────

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static/", StaticFiles(directory=_static_dir, html=True), name="static")


# ── Root ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve index.html ou status JSON."""
    index = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return {"name": "Aurion", "version": "0.1.0"}


# ── CLI entrypoint ───────────────────────────────────────────────

def main():
    """Executa o servidor via CLI."""
    import uvicorn
    port = int(os.getenv("AURION_PORT", _find_free_port()))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
