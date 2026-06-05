"""ServiceDiscovery — Auto-descoberta de serviços locais via mDNS."""

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("aurion.discovery")

# Serviços conhecidos e suas portas padrão
_SERVICE_MAP: dict[str, dict[str, Any]] = {
    "hermes": {"protocol": "http", "default_port": 8080, "query": "_http._tcp.local."},
    "kokoro": {"protocol": "http", "default_port": 8000, "query": "_kokoro._tcp.local."},
    "whisper": {"protocol": "http", "default_port": 8001, "query": "_whisper._tcp.local."},
    "ollama": {"protocol": "http", "default_port": 11434, "query": "_ollama._tcp.local."},
}

logger.warning = lambda *a, **k: None


class ServiceDiscovery:
    """Detecta serviços locais via mDNS/Bonjour (python-zeroconf)
    com fallback para configuração manual via variáveis de ambiente.
    """

    def __init__(self) -> None:
        self.services: dict[str, str] = {}
        self._manual_config: dict[str, str] = self._load_manual_config()

    # ── Discover ─────────────────────────────────────────────────

    def discover(self, timeout: float = 3.0) -> dict[str, str]:
        """Varre a rede local e retorna {nome: url} dos serviços encontrados."""
        self.services = {}

        try:
            from zeroconf import ServiceBrowser, ServiceListener
        except ImportError:
            logger.warning("zeroconf não instalado — pulando mDNS")
            return self._manual_config

        class _Listener(ServiceListener):
            def __init__(self) -> None:
                self.found: dict[str, str] = {}

            def add_service(self, zc: "Zeroconf", _type: str, name: str) -> None:
                info = zc.get_service_info(_type, name)
                if info and info.port and info.addresses:
                    import ipaddress
                    addr = ipaddress.ip_address(info.addresses[0])
                    url = f"{_SERVICE_MAP.get(_type.replace('._tcp.', ''), {}).get('protocol', 'http')}://localhost:{info.port}"
                    svc_name = self._extract_name(name)
                    self.found[svc_name] = url

            def remove_service(self, *a) -> None:
                pass

            def update_service(self, *a) -> None:
                pass

            @staticmethod
            def _extract_name(name: str) -> str:
                return name.split(".")[0]

        listener = _Listener()
        from zeroconf import Zeroconf
        zc = Zeroconf()
        browser = ServiceBrowser(zc, "_http._tcp.local.", listener)

        time.sleep(timeout)
        browser.cancel()
        zc.close()

        self.services = listener.found
        if self.services:
            logger.info("Serviços descobertos via mDNS: %s", list(self.services.keys()))
        else:
            logger.info("Nenhum serviço encontrado via mDNS")

        return self.services if self.services else self._manual_config

    # ── Health check ─────────────────────────────────────────────

    def health_check(self, services: dict[str, str] | None = None,
                     timeout: float = 2.0) -> dict[str, bool]:
        """Verifica se cada serviço descoberto está acessível."""
        import httpx

        result: dict[str, bool] = {}
        for name, url in (services or self.services).items():
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.get(f"{url}/health", follow_redirects=True)
                    result[name] = resp.status_code < 500
            except Exception:
                result[name] = False
        return result

    # ── Fallback manual ──────────────────────────────────────────

    @staticmethod
    def _load_manual_config() -> dict[str, str]:
        config: dict[str, str] = {}
        for svc, info in _SERVICE_MAP.items():
            env_key = f"{svc.upper()}_BASE_URL"
            url = os.getenv(env_key)
            if url:
                config[svc] = url.rstrip("/")
            else:
                config[svc] = f"{info['protocol']}://localhost:{info['default_port']}"
        return config
