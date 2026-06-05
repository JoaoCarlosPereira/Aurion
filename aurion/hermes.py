"""HermesClient — Cliente HTTP para comunicação com Hermes Agent (OpenAI-compatible API)."""

import asyncio
import logging
import os
import threading
from collections.abc import Callable
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logger = logging.getLogger("aurion.hermes")

load_dotenv()


class HermesResponse(BaseModel):
    """Schema de resposta normalizada do Hermes Agent."""

    response: str = Field(description="Resposta gerada pelo Hermes")
    status: str = Field(description="Status da execução ('success' ou 'error')")


class HermesError(Exception):
    """Erro ao comunicar com o Hermes Agent."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


VOICE_SYSTEM_PROMPT = (
    "Você responde por voz a um assistente pessoal. "
    "Seja direta e concisa: no máximo 3 frases curtas em português do Brasil. "
    "Não use meta-comentários, notas entre parênteses, nem diga que vai verificar algo — "
    "apenas entregue o resultado final. "
    "Não mencione que é uma IA. "
    "Mantenha coerência com as mensagens anteriores da mesma conversa."
)

TTS_OPTIMIZATION_PROMPT = (
    "Você transforma respostas em texto otimizado para síntese de voz (TTS) em português do Brasil. "
    "Regras obrigatórias:\n"
    "- Escreva apenas o texto a ser falado, sem markdown, listas, títulos, emojis ou asteriscos\n"
    "- Use frases curtas e naturais, como diálogo falado\n"
    "- Expanda abreviações (ex.: 'Dr.' → 'doutor', 'km' → 'quilômetros')\n"
    "- Converta números, datas, horas e valores para forma falada "
    "(ex.: '15:30' → 'quinze e trinta', 'R$ 10,50' → 'dez reais e cinquenta centavos')\n"
    "- Remova URLs, códigos, blocos técnicos, JSON e meta-comentários\n"
    "- Preserve o significado da resposta original\n"
    "- Não adicione introduções como 'Aqui está' ou 'Texto otimizado'\n"
    "- Responda somente com o texto final pronto para o TTS"
)


class VoiceConversationContext:
    """Histórico user/assistant de uma sessão de conversa por voz."""

    def __init__(
        self,
        max_turns: int | None = None,
        on_start: Callable[[], int] | None = None,
        on_end: Callable[[int], None] | None = None,
    ) -> None:
        limit = max_turns or int(os.getenv("VOICE_CONTEXT_MAX_TURNS", "10"))
        self._max_messages = max(2, limit * 2)
        self._history: list[dict[str, str]] = []
        self._active = False
        self._conversation_id: int | None = None
        self._on_start = on_start
        self._on_end = on_end
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def conversation_id(self) -> int | None:
        with self._lock:
            return self._conversation_id

    def begin(self) -> None:
        with self._lock:
            self._history.clear()
            self._active = True
            self._conversation_id = self._on_start() if self._on_start else None
        logger.info("Contexto de conversa por voz iniciado")

    def end(self) -> None:
        with self._lock:
            if self._on_end and self._conversation_id is not None:
                self._on_end(self._conversation_id)
            self._conversation_id = None
            self._history.clear()
            self._active = False
        logger.info("Contexto de conversa por voz encerrado")

    def snapshot(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._history)

    def append_turn(self, user_text: str, assistant_text: str) -> None:
        with self._lock:
            self._history.append({"role": "user", "content": user_text})
            self._history.append({"role": "assistant", "content": assistant_text})
            if len(self._history) > self._max_messages:
                self._history = self._history[-self._max_messages :]
        logger.info(
            "Contexto de voz atualizado (%d mensagens)",
            len(self.snapshot()),
        )


class HermesClient:
    """Cliente HTTP assíncrono para o Hermes Agent via API OpenAI-compatible.

    Envia comandos via POST para ``{base_url}/v1/chat/completions`` e retorna o
    dicionário de resposta. Suporta retry único com backoff de 1 s e
    timeout configurável (padrão 30 s).
    """

    DEFAULT_TIMEOUT: float = float(os.getenv("HERMES_TIMEOUT", "120"))
    TTS_FORMAT_TIMEOUT: float = float(os.getenv("TTS_HERMES_TIMEOUT", "45"))
    MAX_RETRIES: int = 1
    RETRY_BACKOFF: float = 1.0

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_url = (api_url or HermesClient._load_api_url()).rstrip("/")
        self.api_key = api_key or HermesClient._load_api_key()
        self.model = model or HermesClient._load_model()
        self.timeout = self.DEFAULT_TIMEOUT if timeout is None else timeout
        logger.info(
            "HermesClient inicializado → %s/chat/completions (model=%s, timeout=%ss)",
            self.api_url, self.model, self.timeout,
        )

    @staticmethod
    def _load_api_url() -> str:
        return os.getenv("HERMES_API_URL", "http://localhost:8642/v1")

    @staticmethod
    def _load_api_key() -> str:
        return os.getenv("HERMES_API_KEY", "")

    @staticmethod
    def _load_model() -> str:
        return os.getenv("HERMES_MODEL", "hermes-agent")

    @staticmethod
    def _tts_optimize_enabled() -> bool:
        return os.getenv("TTS_HERMES_OPTIMIZE", "true").lower() not in (
            "0",
            "false",
            "no",
        )

    async def _post_chat(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float | None = None,
    ) -> str:
        """Envia mensagens ao Hermes e retorna o conteúdo da resposta."""
        request_timeout = self.timeout if timeout is None else timeout
        payload = {
            "model": self.model,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    resp = await client.post(
                        f"{self.api_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                content = data["choices"][0]["message"]["content"]
                logger.info(
                    "Hermes respondeu → %d tokens (prompt), %d (completion)",
                    data.get("usage", {}).get("prompt_tokens", 0),
                    data.get("usage", {}).get("completion_tokens", 0),
                )
                return content

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP %s ao chamar Hermes (tentativa %d/%d)",
                    exc.response.status_code,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                )
                last_exc = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BACKOFF)

            except httpx.RequestError as exc:
                logger.warning(
                    "Erro de conexão com Hermes (%s): %s (tentativa %d/%d)",
                    type(exc).__name__,
                    exc,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                )
                last_exc = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BACKOFF)

            except Exception as exc:
                logger.error("Erro inesperado ao comunicar com Hermes: %s", exc)
                raise HermesError(f"Erro inesperado: {exc}") from exc

        assert last_exc is not None
        raise HermesError(
            f"Não foi possível conectar ao Hermes em {self.api_url}",
            status_code=getattr(last_exc, "response", None),
        ) from last_exc

    async def format_for_tts(self, text: str) -> str:
        """Pede ao Hermes um texto otimizado para TTS em pt-BR."""
        source = text.strip()
        if not source or not self._tts_optimize_enabled():
            return text

        messages = [
            {"role": "system", "content": TTS_OPTIMIZATION_PROMPT},
            {
                "role": "user",
                "content": (
                    "Otimize a resposta abaixo para ser falada por um assistente de voz "
                    "em português do Brasil:\n\n"
                    f"{source}"
                ),
            },
        ]
        optimized = (
            await self._post_chat(messages, timeout=self.TTS_FORMAT_TIMEOUT)
        ).strip()
        if not optimized:
            logger.warning("Hermes retornou TTS vazio — usando resposta original")
            return text

        logger.info(
            "TTS otimizado via Hermes (%d → %d caracteres)",
            len(source),
            len(optimized),
        )
        return optimized

    async def send_command(
        self,
        command: str,
        *,
        voice_mode: bool = False,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Envia *command* ao Hermes Agent e retorna a resposta.

        Raises
        ------
        HermesError
            Quando o Hermes não responde ou retorna erro HTTP.
        """
        messages: list[dict[str, str]] = []
        if voice_mode:
            messages.append({"role": "system", "content": VOICE_SYSTEM_PROMPT})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": command})
        if history:
            logger.info(
                "Hermes com contexto: %d mensagem(ns) anterior(es)",
                len(history),
            )

        content = await self._post_chat(messages)
        return {"response": content, "status": "success"}
