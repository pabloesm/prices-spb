import logging
import os
import sys
from pathlib import Path

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


def setup_logger(log_level: int, log_file_path: str = "logger_msgs.log"):
    # Check if the file exists and delete it
    if Path(log_file_path).exists():
        Path(log_file_path).unlink()

    logger_ = logging.getLogger(LOGGER_NAME)
    logger_.setLevel(log_level)

    log_format = "%(asctime)s.%(msecs)03d | %(levelname)-8s | [%(relativepath)s:%(funcName)s:%(lineno)s]: %(message)s"
    date_format = "%Y-%m-%d:%H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Create a StreamHandler for console output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.addFilter(PackagePathFilter())
    stream_handler.setFormatter(formatter)

    # Create a FileHandler to store logs in a file
    try:
        file_handler = logging.FileHandler(log_file_path, mode="a")
        file_handler.setLevel(log_level)
        file_handler.addFilter(PackagePathFilter())
        file_handler.setFormatter(formatter)
        if file_handler not in logger_.handlers:
            logger_.addHandler(file_handler)
    except AttributeError:
        pass

    if stream_handler not in logger_.handlers:
        logger_.addHandler(stream_handler)

    return logger_


def get_logger():
    return logging.getLogger(LOGGER_NAME)


logger = get_logger()
