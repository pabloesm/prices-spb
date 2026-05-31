import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


class Settings(BaseSettings):
    """All environment configuration in one place.

    Reads from the process environment and an optional `.env` file. Required
    fields raise a clear validation error at startup if they are missing.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required
    database_neon_url: str
    api_url_template: str
    cf_url: str
    url_seed: str

    # Optional (only needed for the VPN-backed runs / failover webhook)
    vpn_username: str = ""
    vpn_password: str = ""
    url_webhook_make: str = ""
    log_level: str = "debug"

    @property
    def logging_level(self) -> int:
        """The `log_level` string as a `logging` level constant (defaults to INFO)."""
        return _LOG_LEVELS.get(self.log_level.lower(), logging.INFO)


settings = Settings()
