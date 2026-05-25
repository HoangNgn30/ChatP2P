"""
MongoDB Atlas connection – singleton wrapper around pymongo.
"""

import certifi
from pymongo import MongoClient
from pymongo.database import Database

from utils.constants import DB_NAME
from utils.logger import get_logger

log = get_logger(__name__)


class DatabaseConnection:
    """
    Singleton that holds the MongoClient and exposes the project database.

    Usage::

        db = DatabaseConnection.get_instance("mongodb+srv://...")
        users = db.get_collection("users")
    """

    _instance: "DatabaseConnection | None" = None

    def __init__(self, connection_string: str) -> None:
        log.info("Connecting to MongoDB Atlas …")
        self.client = MongoClient(
            connection_string,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where()
        )
        # Ping to verify connection works
        self.client.admin.command("ping")
        self.db: Database = self.client[DB_NAME]
        log.info("Connected to MongoDB  database=%s", DB_NAME)

    # ── singleton accessor ─────────────────────────────────

    @classmethod
    def get_instance(cls, connection_string: str | None = None) -> "DatabaseConnection":
        if cls._instance is None:
            if not connection_string:
                raise RuntimeError(
                    "DatabaseConnection not initialised – pass a connection_string"
                )
            cls._instance = cls(connection_string)
        return cls._instance

    # ── helpers ────────────────────────────────────────────

    def get_collection(self, name: str):
        """Return a pymongo Collection object."""
        return self.db[name]

    def close(self) -> None:
        """Shutdown the client cleanly."""
        if self.client:
            self.client.close()
            log.info("MongoDB connection closed")
            DatabaseConnection._instance = None
