"""Hermes Bridge — cliente HTTP REST assíncrono para o Hermes Agent.

Implementa a comunicação com o Hermes Agent conforme a TechSpec (Seções 5.1,
10.1 e 10.2) e a ADR-002, usando ``httpx`` como cliente HTTP assíncrono.

Princípios de projeto:

- **Assíncrono**: todas as operações de E/S usam ``async``/``await`` e o
  ``httpx.AsyncClient``.
- **Retry com backoff exponencial**: comandos são reenviados até 3 tentativas
  (configurável) com atraso crescente entre elas (TechSpec Seção 10.1). Erros
  4xx (exceto 429) não são reenviados, pois indicam falha do cliente.
- **Tratamento de erros robusto**: erros HTTP (4xx/5xx) e exceções de rede
  (timeout, conexão recusada) são convertidos em ``HermesError`` com um
  ``APIError`` padronizado (TechSpec Seção 10.2).
- **Configuração**: endpoint e ``auth_token`` são lidos da configuração
  (``config/settings.py``, task_03). O token é enviado no header
  ``Authorization``.
- **Import lazy**: ``httpx`` é importado dentro do factory do cliente para que o
  módulo seja carregável em ambientes sem a dependência; os testes substituem o
  cliente/transport por mocks (sem rede real).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config.models import HermesConfig
from models.response import APIError, HermesResponse

logger = logging.getLogger(__name__)

# Caminho do endpoint de envio de comando no Hermes Agent (TechSpec Seção 5.1).
HERMES_COMMAND_PATH = "/api/completion"
# Caminho usado para teste de conectividade (health check leve).
HERMES_HEALTH_PATH = "/health"

# Códigos de erro padronizados (TechSpec Seção 10.2).
ERR_UNAVAILABLE = "HERMES_UNAVAILABLE"
ERR_TIMEOUT = "HERMES_TIMEOUT"
ERR_HTTP = "HERMES_HTTP_ERROR"
ERR_UNAUTHORIZED = "HERMES_UNAUTHORIZED"
ERR_INVALID_RESPONSE = "HERMES_INVALID_RESPONSE"

# Parâmetros padrão de retry/backoff (TechSpec Seção 10.1).
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5  # segundos
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_TIMEOUT = 30.0  # segundos


class HermesError(Exception):
    """Erro de comunicação com o Hermes, carregando um ``APIError`` padronizado.

    Expõe o atributo ``error`` (``APIError``) com ``code``, ``message`` e
    ``details``, permitindo à camada de API retornar uma resposta de erro
    consistente em PT-BR.
    """

    def __init__(self, error: APIError) -> None:
        super().__init__(error.message)
        self.error = error

    @property
    def code(self) -> str:
        return self.error.code


class HermesBridge:
    """Cliente HTTP REST assíncrono para o Hermes Agent.

    Lê endpoint e token da ``HermesConfig`` e expõe ``send_command`` (envio de
    comando com retry/backoff) e ``test_connection`` (teste de conectividade).
    """

    def __init__(
        self,
        config: HermesConfig | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._config = config or HermesConfig()
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._timeout = timeout

    @property
    def config(self) -> HermesConfig:
        return self._config

    @property
    def endpoint(self) -> str:
        """Endpoint base do Hermes, sem barra final."""
        return self._config.endpoint.rstrip("/")

    @property
    def max_retries(self) -> int:
        return self._max_retries

    # --- API pública ---------------------------------------------------------

    async def send_command(self, message: str) -> HermesResponse:
        """Envia um comando de texto ao Hermes e retorna a resposta padronizada.

        Faz ``POST`` ao endpoint configurado com o corpo ``{"message": ...}`` e o
        header ``Authorization``. Em caso de falha transitória (5xx, 429, timeout
        ou erro de conexão), reenvia com backoff exponencial até ``max_retries``.
        Erros 4xx definitivos (ex.: 401) não são reenviados.

        Levanta ``HermesError`` (com ``APIError``) se todas as tentativas
        falharem ou diante de um erro definitivo.
        """
        message = (message or "").strip()
        if not message:
            raise HermesError(
                APIError(
                    code=ERR_INVALID_RESPONSE,
                    message="Mensagem vazia: nada a enviar ao Hermes.",
                )
            )

        url = f"{self.endpoint}{HERMES_COMMAND_PATH}"
        payload = {"message": message}
        response = await self._request_with_retry("POST", url, json=payload)
        return self._parse_response(response)

    async def test_connection(self) -> bool:
        """Testa a conectividade com o Hermes, retornando ``True`` em sucesso.

        Faz uma requisição leve ao endpoint de health do Hermes. Qualquer
        resposta HTTP bem-sucedida (2xx) é considerada sucesso. Falhas de rede,
        timeout ou status de erro retornam ``False`` (degradação graciosa, sem
        levantar exceção).
        """
        url = f"{self.endpoint}{HERMES_HEALTH_PATH}"
        try:
            await self._request_with_retry("GET", url, max_retries=1)
            return True
        except HermesError as exc:
            logger.warning("Teste de conexão com o Hermes falhou: %s", exc.error.message)
            return False

    # --- Internos ------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Monta os headers da requisição, incluindo ``Authorization``."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        token = self._config.auth_token
        if token:
            # Suporta tokens já no formato "Bearer ..." ou apenas o valor cru.
            headers["Authorization"] = (
                token if token.lower().startswith("bearer ") else f"Bearer {token}"
            )
        return headers

    def _create_client(self):
        """Cria o ``httpx.AsyncClient`` (ponto de mock nos testes).

        Import lazy de ``httpx``; levanta ``HermesError`` se indisponível.
        """
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercido via mock
            raise HermesError(
                APIError(
                    code=ERR_UNAVAILABLE,
                    message="httpx não está instalado; Hermes Bridge indisponível.",
                )
            ) from exc

        return httpx.AsyncClient(timeout=self._timeout, headers=self._build_headers())

    async def _backoff(self, attempt: int) -> None:
        """Aguarda o atraso de backoff exponencial para a tentativa informada.

        ``attempt`` é baseado em zero: a primeira espera usa ``backoff_base``,
        a segunda ``backoff_base * factor``, e assim por diante.
        """
        delay = self._backoff_base * (self._backoff_factor**attempt)
        await asyncio.sleep(delay)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ):
        """Executa a requisição HTTP com retry e backoff exponencial.

        Reenvia em erros transitórios (5xx, 429, timeout, erro de conexão) até
        atingir o limite de tentativas. Erros 4xx definitivos abortam de
        imediato. Retorna o objeto de resposta do httpx em caso de sucesso ou
        levanta ``HermesError`` quando esgotadas as tentativas.
        """
        # ``httpx`` é importado aqui para acessar suas classes de exceção sem
        # tornar o import obrigatório no carregamento do módulo.
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercido via mock
            raise HermesError(
                APIError(
                    code=ERR_UNAVAILABLE,
                    message="httpx não está instalado; Hermes Bridge indisponível.",
                )
            ) from exc

        attempts = max_retries if max_retries is not None else self._max_retries
        last_error: APIError | None = None

        client = self._create_client()
        async with client:
            for attempt in range(attempts):
                try:
                    response = await client.request(method, url, json=json)
                except httpx.TimeoutException as exc:
                    last_error = APIError(
                        code=ERR_TIMEOUT,
                        message="Tempo limite excedido ao contatar o Hermes.",
                        details={"attempt": attempt + 1, "error": str(exc)},
                    )
                    logger.warning("Timeout ao contatar o Hermes (tentativa %d).", attempt + 1)
                except httpx.HTTPError as exc:
                    # Cobre ConnectError, ReadError e demais erros de transporte.
                    last_error = APIError(
                        code=ERR_UNAVAILABLE,
                        message="Hermes indisponível: falha de conexão.",
                        details={"attempt": attempt + 1, "error": str(exc)},
                    )
                    logger.warning("Erro de conexão com o Hermes (tentativa %d).", attempt + 1)
                else:
                    status = response.status_code
                    if status < 400:
                        return response
                    # Erro 4xx (exceto 429) é definitivo: não reenviar.
                    if 400 <= status < 500 and status != 429:
                        raise HermesError(self._http_error(status))
                    # 5xx ou 429: erro transitório, elegível a retry.
                    last_error = self._http_error(status)
                    logger.warning(
                        "Hermes retornou status %d (tentativa %d).", status, attempt + 1
                    )

                # Aguarda o backoff antes da próxima tentativa (se houver).
                if attempt < attempts - 1:
                    await self._backoff(attempt)

        # Esgotadas as tentativas: levanta o último erro registrado.
        if last_error is None:  # pragma: no cover - defensivo
            last_error = APIError(
                code=ERR_UNAVAILABLE, message="Falha desconhecida ao contatar o Hermes."
            )
        raise HermesError(last_error)

    def _http_error(self, status: int) -> APIError:
        """Constrói um ``APIError`` adequado para um status HTTP de erro."""
        if status in (401, 403):
            return APIError(
                code=ERR_UNAUTHORIZED,
                message="Não autorizado pelo Hermes: verifique o token de acesso.",
                details={"status_code": status},
            )
        if status >= 500:
            return APIError(
                code=ERR_UNAVAILABLE,
                message=f"Hermes indisponível: erro {status} no servidor.",
                details={"status_code": status},
            )
        return APIError(
            code=ERR_HTTP,
            message=f"Erro {status} retornado pelo Hermes.",
            details={"status_code": status},
        )

    def _parse_response(self, response) -> HermesResponse:
        """Converte a resposta HTTP do Hermes em ``HermesResponse``.

        Tenta decodificar o corpo como JSON e extrair o texto de resposta dos
        campos usuais (``reply``, ``response``, ``message``, ``text`` ou
        ``content``). Se o corpo não for JSON, usa o texto cru. Levanta
        ``HermesError`` apenas se nenhum conteúdo puder ser extraído.
        """
        try:
            data = response.json()
        except Exception:  # noqa: BLE001 - corpo não-JSON
            data = None

        if isinstance(data, dict):
            reply = (
                data.get("reply")
                or data.get("response")
                or data.get("message")
                or data.get("text")
                or data.get("content")
            )
            if reply is None:
                raise HermesError(
                    APIError(
                        code=ERR_INVALID_RESPONSE,
                        message="Resposta do Hermes sem campo de texto reconhecível.",
                        details={"raw": data},
                    )
                )
            return HermesResponse(
                reply=str(reply), status_code=response.status_code, raw=data
            )

        # Corpo não-JSON: usa o texto cru, se houver.
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise HermesError(
                APIError(
                    code=ERR_INVALID_RESPONSE,
                    message="Resposta vazia do Hermes.",
                )
            )
        return HermesResponse(reply=text, status_code=response.status_code, raw={})
