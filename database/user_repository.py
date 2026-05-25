"""
User repository – CRUD for the ``users`` collection.
"""

from datetime import datetime
from utils.timezone import TZ_UTC7

import bcrypt
from pymongo.collection import Collection

from database.db_connection import DatabaseConnection
from utils.constants import COLLECTION_USERS, STATUS_OFFLINE, STATUS_ONLINE
from utils.logger import get_logger

log = get_logger(__name__)


class UserRepository:
    """Manages user accounts stored in MongoDB."""

    def __init__(self, db: DatabaseConnection) -> None:
        self.col: Collection = db.get_collection(COLLECTION_USERS)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.col.create_index("username", unique=True)
        self.col.create_index("status")

    # ── create ─────────────────────────────────────────────

    def create_user(self, username: str, password: str, public_key: str) -> bool:
        """
        Register a new user.  Returns True on success, False if username
        already exists.
        """
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            self.col.insert_one(
                {
                    "username": username,
                    "password_hash": password_hash,
                    "public_key": public_key,
                    "created_at": datetime.now(TZ_UTC7),
                    "last_seen": datetime.now(TZ_UTC7),
                    "status": STATUS_OFFLINE,
                }
            )
            log.info("User created: %s", username)
            return True
        except Exception as exc:
            log.warning("create_user failed for %s: %s", username, exc)
            return False

    # ── read ───────────────────────────────────────────────

    def get_user(self, username: str) -> dict | None:
        return self.col.find_one({"username": username}, {"_id": 0})

    def get_online_users(self) -> list[dict]:
        return list(
            self.col.find(
                {"status": STATUS_ONLINE},
                {"_id": 0, "username": 1, "public_key": 1},
            )
        )

    # ── update ─────────────────────────────────────────────

    def update_status(self, username: str, status: str) -> None:
        update_fields = {"status": status, "last_seen": datetime.now(TZ_UTC7)}
        self.col.update_one({"username": username}, {"$set": update_fields})
        log.debug("Status updated: %s → %s", username, status)

    def update_public_key(self, username: str, public_key: str) -> None:
        self.col.update_one(
            {"username": username}, {"$set": {"public_key": public_key}}
        )

    def update_last_seen(self, username: str) -> None:
        self.col.update_one(
            {"username": username},
            {"$set": {"last_seen": datetime.now(TZ_UTC7)}},
        )

    # ── auth ───────────────────────────────────────────────

    def verify_password(self, username: str, password: str) -> bool:
        """Return True if *password* matches the stored hash."""
        user = self.col.find_one({"username": username}, {"password_hash": 1})
        if not user:
            return False
        return bcrypt.checkpw(password.encode(), user["password_hash"].encode())
