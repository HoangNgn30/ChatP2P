"""
Configuration loader – reads settings from .env file.
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


class Config:
    """Centralised configuration read from environment variables."""

    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")

    # Bootstrap server
    BOOTSTRAP_HOST: str = os.getenv("BOOTSTRAP_HOST", "0.0.0.0")
    BOOTSTRAP_PORT: int = int(os.getenv("BOOTSTRAP_PORT", "9000"))

    # Peer defaults
    PEER_HOST: str = os.getenv("PEER_HOST", "0.0.0.0")
    PEER_PORT: int = int(os.getenv("PEER_PORT", "5001"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Heartbeat
    HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "15"))
    HEARTBEAT_TIMEOUT: int = int(os.getenv("HEARTBEAT_TIMEOUT", "30"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of configuration problems (empty = OK)."""
        problems: list[str] = []
        if not cls.MONGODB_URI:
            problems.append("MONGODB_URI is not set in .env")
        return problems
