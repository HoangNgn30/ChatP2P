"""
Coloured logging setup shared by every module.
"""

import logging
import sys

import colorlog

from utils.config import Config


def get_logger(name: str) -> logging.Logger:
    """
    Create (or retrieve) a logger with coloured console output.

    Usage::

        from utils.logger import get_logger
        log = get_logger(__name__)
        log.info("Hello %s", "world")
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = colorlog.StreamHandler(sys.stdout)
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    return logger
