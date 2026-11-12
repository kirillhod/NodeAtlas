"""Namespaced logging for NodeAtlas."""

from __future__ import annotations

import logging

LOGGER_NAME = "node_atlas"
_configured = False


def _configure(debug: bool = False) -> None:
    global _configured
    if _configured:
        return
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[NodeAtlas] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    _configured = True


def get_logger(debug: bool = False) -> logging.Logger:
    _configure(debug)
    return logging.getLogger(LOGGER_NAME)
