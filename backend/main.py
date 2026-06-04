from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from api.websocket import WebSocketManager, set_ws_manager
from config.settings import ConfigManager, init_config_manager, reset_config_manager
from db.database import Database, init_database, close_database
from svc.hermes_bridge import HermesBridge
from svc.listening import ListeningConfig, ListeningService
from svc.stt import STTService
from svc.tts import TTSService
from svc.wakeword import WakeWordEngine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicacao: inicializacao e shutdown ordenado."""
    # --- Startup -----------------------------------------------------------
    logger.info("Iniciando Aurion...")

    # 1. Config Manager
    config_manager = await init_config_manager()
    config = await config_manager.get()

    # 2. Database
    db_path = config.database.path
    await init_database(db_path)
    logger.info("Banco de dados inicializado: %s", db_path)

    # 3. WebSocket Manager
    ws_manager = WebSocketManager()
    set_ws_manager(ws_manager)

    # 4. Services (lazy — created per-request or via Listening Service)
    #    The Listening Service gets injected factories.

    # 5. Listening Service (optional — runs in a daemon thread)
    try:
        from config.settings import get_config_manager as _gcm

        cm = _gcm()
        cfg = await cm.get()

        wakeword = WakeWordEngine(cfg.wake_word)
        stt = STTService(cfg.stt)
        hermes = HermesBridge(cfg.hermes)
        tts = TTSService(cfg.tts)

        repo = __import__("db.repo", fromlist=["InteractionRepository"]).InteractionRepository(
            __import__("db.database", fromlist=["get_database"]).get_database()
        )

        listening_config = ListeningConfig(
            sample_rate=cfg.audio.sample_rate,
            channels=cfg.audio.channels,
            chunk_size=cfg.audio.chunk_size,
            silence_threshold=cfg.audio.silence_threshold,
        )

        service = ListeningService(
            wakeword=wakeword,
            stt=stt,
            hermes=hermes,
            tts=tts,
            repository=repo,
            config=listening_config,
            on_state=ws_manager.on_state_from_thread,
            on_audio=lambda chunk: asyncio.create_task(
                _broadcast_audio(ws_manager, chunk)
            ),
        )

        app.state.listening_service = service
        service.start()
        logger.info("Listening Service iniciado.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Listening Service nao pudo iniciar: %s", exc)

    logger.info("Aurion pronto.")

    yield

    # --- Shutdown ------------------------------------------------------------
    logger.info("Encerrando Aurion...")

    svc = getattr(app.state, "listening_service", None)
    if svc is not None and svc.is_running:
        svc.stop(timeout=5.0)

    await close_database()
    await reset_config_manager()
    set_ws_manager(None)
    logger.info("Aurion encerrado.")


import asyncio as _asyncio


async def _broadcast_audio(manager: WebSocketManager, chunk: bytes) -> None:
    """Roteia chunks de audio TTS para clientes WebSocket de audio."""
    session_ids = list(manager._audio_clients.keys())
    for sid in session_ids:
        await manager.send_audio_chunk(sid, chunk)


# --- FastAPI app -------------------------------------------------------------

app = FastAPI(
    title="Aurion",
    description="Assistente pessoal por voz — servidor local + web app",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/state")
async def get_state():
    """Retorna o estado corrente do Listening Service e métricas."""
    svc = getattr(app.state, "listening_service", None)
    if svc is not None:
        return {
            "listening": svc.is_running,
            "state": svc.state,
            "degraded": svc.is_degraded,
            "latencies": svc.last_latencies,
        }
    return {"listening": False, "state": "idle", "degraded": False, "latencies": {}}
