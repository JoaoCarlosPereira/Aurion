"""Registro de todos os routers da API REST do Aurion.

Centraliza o ``include_router`` de cada módulo de endpoint, facilitando a
manutenção e a adição de novos recursos.

Os módulos de router são:

- ``config`` — GET/PUT /api/config + validação avançada de áudio (task_03, task_11)
- ``command`` — POST /api/command + GET /api/command/{id} (task_05)
- ``history`` — GET /api/history + DELETE /api/history (task_05)
- ``test`` — POST /api/test/* — endpoints de diagnóstico (task_11)
- ``websocket`` — WebSocket /ws/* (task_10)
"""

from fastapi import APIRouter

from api.command import router as command_router
from api.config import router as config_router
from api.history import router as history_router
from api.test import router as test_router
from api.websocket import router as ws_router

# Router raiz agrupando todos os sub-rotas sob ``/api``.
api_router = APIRouter()

api_router.include_router(config_router)
api_router.include_router(command_router)
api_router.include_router(history_router)
api_router.include_router(test_router)
api_router.include_router(ws_router)
