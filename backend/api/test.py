"""Endpoints REST de teste de conexão (POST /api/test/*).

Expõe os testes de conectividade/funcionamento dos serviços externos do Aurion,
conforme a TechSpec (Seção 3.1):

- ``POST /api/test/hermes`` — testa a conexão com o Hermes Agent.
- ``POST /api/test/stt`` — valida o carregamento/funcionamento do serviço STT.
- ``POST /api/test/tts`` — valida o TTS ativo (edge-tts ou externo), incluindo
  um teste de *streaming* (verifica que ao menos um chunk de áudio é produzido).
  Quando o TTS externo está habilitado mas falha, o serviço degrada graciosamente
  para o edge-tts (fallback) — comportamento exercido por ``TTSService.synthesize``.
- ``GET /api/test/tts/voices`` — lista as vozes PT-BR disponíveis para o TTS.

Todos os endpoints aplicam um *rate limiting* básico (janela deslizante em
memória) para evitar execução indesejada/abuso dos testes, conforme os
requisitos da task_11.

O wiring final (registro do router e provisão do ``ConfigManager``) é feito na
task_18. Este módulo apenas expõe o objeto ``router`` e as dependências/factories
(``get_config_manager_dep``, ``get_hermes_bridge_factory``,
``get_stt_service_factory``, ``get_tts_service_factory``), que podem ser
sobrescritas via ``app.dependency_overrides`` em testes (sem rede, hardware ou
binários reais — apenas mocks).
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from config.settings import ConfigManager, get_config_manager
from svc.hermes_bridge import HermesBridge
from svc.stt import STTConfig as ServiceSTTConfig
from svc.stt import STTService
from svc.tts import TTSConfig as ServiceTTSConfig
from svc.tts import TTSService

router = APIRouter(prefix="/api/test", tags=["test"])


# --- Parâmetros e estado do rate limiting ------------------------------------

# Janela deslizante: no máximo ``RATE_LIMIT_MAX`` requisições por
# ``RATE_LIMIT_WINDOW_SECONDS`` por cliente (identificado pelo IP de origem).
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 10.0


class _RateLimiter:
    """Rate limiter simples de janela deslizante em memória (por chave).

    Mantém, para cada chave (ex.: IP do cliente), os timestamps das requisições
    recentes. É *thread-safe* (protegido por ``Lock``) e suficiente para a
    proteção básica exigida pela task_11 — não substitui um limitador distribuído
    em produção. O ``time_func`` é injetável para tornar os testes determinísticos.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_MAX,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._time = time_func
        self._lock = Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Registra uma requisição e indica se ela está dentro do limite.

        Retorna ``True`` quando a requisição é permitida; ``False`` quando o
        limite da janela foi excedido para a chave informada.
        """
        now = self._time()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            # Descarta os registros mais antigos que a janela atual.
            limit = now - self._window
            while bucket and bucket[0] <= limit:
                bucket.popleft()
            if len(bucket) >= self._max:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """Limpa todo o estado acumulado (uso em testes)."""
        with self._lock:
            self._hits.clear()


# Instância única usada pela dependência padrão. Em testes, a dependência
# ``get_rate_limiter`` pode ser sobrescrita por um limitador isolado.
_rate_limiter = _RateLimiter()


# --- Modelos de resposta -----------------------------------------------------


class TestResult(BaseModel):
    """Resultado estruturado de um teste de conexão/funcionamento.

    - ``success``: indica se o teste foi bem-sucedido.
    - ``message``: mensagem descritiva em PT-BR para exibição na UI.
    - ``details``: informações adicionais (ex.: endpoint, engine, vozes).
    """

    success: bool
    message: str
    details: dict[str, Any] = {}


class VoicesResult(BaseModel):
    """Lista de vozes disponíveis para o TTS."""

    voices: list[str]
    count: int


# --- Dependências (sobrescritíveis em testes) --------------------------------


def get_config_manager_dep() -> ConfigManager:
    """Dependência que fornece o Config Manager (singleton da aplicação).

    Pode ser sobrescrita em testes via ``app.dependency_overrides``.
    """
    return get_config_manager()


def get_rate_limiter() -> _RateLimiter:
    """Fornece o rate limiter dos endpoints de teste.

    Isolada como dependência para permitir substituição/limpeza em testes.
    """
    return _rate_limiter


def get_hermes_bridge_factory() -> Callable[[ConfigManager], HermesBridge]:
    """Fornece a factory que cria um ``HermesBridge`` a partir da configuração.

    Isolada como dependência para permitir substituição por um cliente mockado
    em testes (sem rede real).
    """

    def _factory(manager: ConfigManager) -> HermesBridge:
        config = manager._config  # type: ignore[attr-defined]
        # Quando ainda não carregado, usa a configuração padrão; o teste real de
        # produção é feito após a inicialização do Config Manager (task_18).
        hermes_config = config.hermes if config is not None else None
        return HermesBridge(hermes_config)

    return _factory


def get_stt_service_factory() -> Callable[[ConfigManager], STTService]:
    """Fornece a factory que cria um ``STTService`` a partir da configuração.

    Mapeia o bloco ``stt`` da configuração da aplicação para a ``STTConfig`` do
    serviço (que tem campos adicionais, como ``timeout``). Em testes, a factory
    é substituída por uma que injeta um transcritor mockado (sem whisper.cpp).
    """

    def _factory(manager: ConfigManager) -> STTService:
        config = manager._config  # type: ignore[attr-defined]
        if config is None:
            return STTService()
        stt = config.stt
        service_config = ServiceSTTConfig(
            engine=stt.engine,
            model=stt.model,
            language=stt.language,
            threads=stt.threads,
            beam_size=stt.beam_size,
            max_context=stt.max_context,
        )
        return STTService(service_config)

    return _factory


def get_tts_service_factory() -> Callable[[ConfigManager], TTSService]:
    """Fornece a factory que cria um ``TTSService`` a partir da configuração.

    Mapeia o bloco ``tts`` (incluindo ``tts.external``) da configuração da
    aplicação para a ``TTSConfig`` do serviço. Em testes, a factory é substituída
    por uma que injeta engines mockadas (sem edge-tts/httpx/rede).
    """

    def _factory(manager: ConfigManager) -> TTSService:
        config = manager._config  # type: ignore[attr-defined]
        if config is None:
            return TTSService()
        tts = config.tts
        external = tts.external
        from svc.tts import ExternalTTSConfig as ServiceExternalTTSConfig

        service_config = ServiceTTSConfig(
            engine=tts.engine,
            voice=tts.voice,
            rate=tts.rate,
            volume=tts.volume,
            external=ServiceExternalTTSConfig(
                enabled=external.enabled,
                endpoint=external.endpoint,
                api_key=external.api_key,
                params=dict(external.params),
                format=external.format,
                timeout=external.timeout,
            ),
        )
        return TTSService(service_config)

    return _factory


# --- Helpers internos --------------------------------------------------------


def _client_key(request: Request) -> str:
    """Deriva a chave do rate limiter a partir do IP de origem da requisição."""
    client = request.client
    return client.host if client is not None else "desconhecido"


def _enforce_rate_limit(request: Request, limiter: _RateLimiter) -> None:
    """Aplica o rate limiting; levanta ``429`` quando o limite é excedido."""
    if not limiter.allow(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMITED",
                "message": (
                    "Muitas requisições de teste em curto período. "
                    "Aguarde alguns segundos e tente novamente."
                ),
            },
        )


# --- Endpoints ---------------------------------------------------------------


@router.post("/hermes", response_model=TestResult)
async def test_hermes(
    request: Request,
    manager: ConfigManager = Depends(get_config_manager_dep),
    limiter: _RateLimiter = Depends(get_rate_limiter),
    bridge_factory: Callable[[ConfigManager], HermesBridge] = Depends(
        get_hermes_bridge_factory
    ),
) -> TestResult:
    """Testa a conexão com o Hermes Agent usando a configuração atual.

    Nunca levanta exceção de rede: o ``HermesBridge.test_connection`` aplica
    degradação graciosa e retorna ``False`` em caso de falha. Retorna um
    ``TestResult`` com a mensagem descritiva e o endpoint testado.
    """
    _enforce_rate_limit(request, limiter)
    # Garante que a configuração esteja carregada antes de montar o cliente.
    await manager.get()
    bridge = bridge_factory(manager)
    success = await bridge.test_connection()
    message = (
        "Conexão com o Hermes Agent bem-sucedida."
        if success
        else "Não foi possível conectar ao Hermes Agent."
    )
    return TestResult(
        success=success,
        message=message,
        details={"endpoint": bridge.endpoint},
    )


@router.post("/stt", response_model=TestResult)
async def test_stt(
    request: Request,
    manager: ConfigManager = Depends(get_config_manager_dep),
    limiter: _RateLimiter = Depends(get_rate_limiter),
    stt_factory: Callable[[ConfigManager], STTService] = Depends(
        get_stt_service_factory
    ),
) -> TestResult:
    """Testa o serviço STT validando o carregamento do modelo configurado.

    Usa ``STTService.test_model``, que retorna ``True`` se um transcritor
    (whisper.cpp ou fallback) pôde ser carregado e ``False`` caso contrário
    (ex.: modelo inexistente ou whisper.cpp indisponível) — sem propagar
    exceções (degradação graciosa, TechSpec Seção 10).
    """
    _enforce_rate_limit(request, limiter)
    await manager.get()
    service = stt_factory(manager)
    success = await service.test_model()
    message = (
        "Serviço STT operacional: modelo carregado com sucesso."
        if success
        else (
            "Falha ao carregar o modelo STT. Verifique o modelo configurado e "
            "a disponibilidade do whisper.cpp."
        )
    )
    return TestResult(
        success=success,
        message=message,
        details={
            "engine": service.config.engine,
            "model": service.config.model,
        },
    )


@router.post("/tts", response_model=TestResult)
async def test_tts(
    request: Request,
    manager: ConfigManager = Depends(get_config_manager_dep),
    limiter: _RateLimiter = Depends(get_rate_limiter),
    tts_factory: Callable[[ConfigManager], TTSService] = Depends(
        get_tts_service_factory
    ),
) -> TestResult:
    """Testa o serviço TTS verificando a produção de áudio por *streaming*.

    Executa ``TTSService.synthesize`` com um texto curto e considera o teste
    bem-sucedido se ao menos um chunk de áudio for produzido. Isso valida o
    *streaming* de ponta a ponta: quando o TTS externo está habilitado, o
    serviço tenta usá-lo via streaming chunked e, em caso de falha, recorre
    automaticamente ao edge-tts (fallback). A engine que efetivamente produziu
    o áudio é informada em ``details.engine``.
    """
    _enforce_rate_limit(request, limiter)
    await manager.get()
    service = tts_factory(manager)
    external_enabled = service.config.external.enabled

    chunks = 0
    error: str | None = None
    try:
        async for chunk in service.synthesize("teste de voz"):
            if chunk:
                chunks += 1
    except Exception as exc:  # noqa: BLE001 - degradação graciosa
        # Ambas as engines falharam: reporta erro sem derrubar o servidor.
        error = str(exc)

    success = chunks > 0
    if success:
        message = "Serviço TTS operacional: áudio gerado via streaming."
    elif error is not None:
        message = f"Falha no serviço TTS: {error}"
    else:
        message = "Serviço TTS não produziu áudio."

    return TestResult(
        success=success,
        message=message,
        details={
            "voice": service.config.voice,
            "external_enabled": external_enabled,
            "chunks": chunks,
        },
    )


@router.get("/tts/voices", response_model=VoicesResult)
async def list_tts_voices(
    request: Request,
    manager: ConfigManager = Depends(get_config_manager_dep),
    limiter: _RateLimiter = Depends(get_rate_limiter),
    tts_factory: Callable[[ConfigManager], TTSService] = Depends(
        get_tts_service_factory
    ),
) -> VoicesResult:
    """Lista as vozes PT-BR disponíveis para o serviço TTS."""
    _enforce_rate_limit(request, limiter)
    await manager.get()
    service = tts_factory(manager)
    voices = await service.list_voices()
    return VoicesResult(voices=voices, count=len(voices))
