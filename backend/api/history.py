"""Endpoints REST de histórico de interações (TechSpec Seção 3.1).

Expõe:

- ``GET /api/history?limit=50&offset=0&search=termo`` — lista interações
  paginadas, com busca opcional por texto (``input_text``/``output_text``).
- ``GET /api/history/{id}`` — retorna uma interação específica.
- ``DELETE /api/history`` — remove todo o histórico.

Toda a persistência é delegada ao ``InteractionRepository`` (task_02). O wiring
final (registro do router e provisão do repositório) é feito na task_18; este
módulo apenas expõe o objeto ``router`` e a dependência ``get_repository_dep``,
sobrescritível via ``app.dependency_overrides`` em testes (banco em memória).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from db.repo import InteractionRepository
from models.interaction import Interaction
from models.response import APIError, DeleteResult, HistoryList

router = APIRouter(prefix="/api/history", tags=["history"])

# Código de erro padronizado desta camada (TechSpec Seção 10.2).
ERR_NOT_FOUND = "INTERACTION_NOT_FOUND"


def get_repository_dep() -> InteractionRepository:
    """Dependência que fornece o repositório de interações.

    O wiring real (banco singleton) é feito na task_18. Em testes, é sobrescrita
    via ``app.dependency_overrides`` por um repositório em memória.
    """
    from db.database import get_database

    return InteractionRepository(get_database())


@router.get("", response_model=HistoryList)
async def list_history(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    repo: InteractionRepository = Depends(get_repository_dep),
) -> HistoryList:
    """Lista interações paginadas (mais recentes primeiro), com busca opcional.

    ``search`` aplica um filtro por texto sobre ``input_text``/``output_text``.
    """
    items = await repo.list_interactions(limit=limit, offset=offset, search=search)
    return HistoryList(items=items, limit=limit, offset=offset, count=len(items))


@router.delete("", response_model=DeleteResult)
async def clear_history(
    repo: InteractionRepository = Depends(get_repository_dep),
) -> DeleteResult:
    """Remove todo o histórico de interações e retorna a quantidade removida."""
    deleted = await repo.delete_all_interactions()
    return DeleteResult(deleted=deleted)


@router.get("/{interaction_id}", response_model=Interaction)
async def get_history_item(
    interaction_id: str,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> Interaction:
    """Retorna uma interação específica do histórico ou ``404`` se inexistente."""
    interaction = await repo.get_interaction_by_id(interaction_id)
    if interaction is None:
        raise HTTPException(
            status_code=404,
            detail=APIError(
                code=ERR_NOT_FOUND,
                message="Interação não encontrada.",
                details={"id": interaction_id},
            ).model_dump(),
        )
    return interaction
