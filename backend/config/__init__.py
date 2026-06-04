"""Pacote de configuração da aplicação (Config Manager).

Reexporta os principais símbolos do gerenciador de configurações e dos modelos
para facilitar o uso pelos demais módulos.
"""

from config.models import (
    AppConfig,
    AppConfigUpdate,
    AudioConfig,
    DatabaseConfig,
    ExternalTTSConfig,
    HermesConfig,
    STTConfig,
    TTSConfig,
    WakeWordConfig,
)
from config.settings import (
    ConfigManager,
    get_config_manager,
    init_config_manager,
    reset_config_manager,
)

__all__ = [
    "AppConfig",
    "AppConfigUpdate",
    "AudioConfig",
    "DatabaseConfig",
    "ExternalTTSConfig",
    "HermesConfig",
    "STTConfig",
    "TTSConfig",
    "WakeWordConfig",
    "ConfigManager",
    "get_config_manager",
    "init_config_manager",
    "reset_config_manager",
]
