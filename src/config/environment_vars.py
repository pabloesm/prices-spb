import logging
import os
from typing import Optional


class EnvironmentVars:
    def get_logging_level(self):
        return self._parse_logging_level(
            self._get_optional_environment_variable("LOG_LEVEL", "debug")
        )

    @staticmethod
    def _get_required_environment_variable(name: str, fallback: Optional[str] = None) -> str:
        val = os.environ.get(name, fallback)
        if not val:
            raise ValueError(f"Environment variable {name} not defined, exiting...")
        return val

    @staticmethod
    def _get_optional_environment_variable(name: str, fallback: Optional[str] = None) -> str:
        val = os.environ.get(name, fallback)
        if not val:
            if not fallback:
                return ""
            return fallback
        return val

    @staticmethod
    def _parse_logging_level(var_name: str) -> int:
        log_level_map = {
            "critical": logging.CRITICAL,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "info": logging.INFO,
            "debug": logging.DEBUG,
        }

        if var_name.lower() not in log_level_map:
            return log_level_map["info"]

        return log_level_map[var_name.lower()]
