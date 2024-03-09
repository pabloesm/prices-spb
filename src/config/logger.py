import logging
import os
import sys

from src.config.environment_vars import EnvironmentVars

LOGGER_NAME = "prices-spb"


class PackagePathFilter(logging.Filter):
    """Custom filter to get relative path."""

    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            if not path.endswith(os.sep):
                path += os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True


def setup_logger(log_level: int):
    logger_obj = logging.getLogger(LOGGER_NAME)
    logger_obj.setLevel(log_level)

    log_format = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | "
        "[%(relativepath)s:%(funcName)s:%(lineno)s]: %(message)s"
    )
    date_format = "%Y-%m-%d:%H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Create a StreamHandler for console output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.addFilter(PackagePathFilter())
    stream_handler.setFormatter(formatter)

    if not any(isinstance(handler, logging.StreamHandler) for handler in logger_obj.handlers):
        logger_obj.addHandler(stream_handler)

    return logger_obj


def get_logger():
    return logging.getLogger(LOGGER_NAME)


logger = get_logger()
