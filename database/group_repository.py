"""
Group repository – CRUD for the ``groups`` collection.
"""

import uuid
from datetime import datetime
from utils.timezone import TZ_UTC7

from pymongo.collection import Collection

from database.db_connection import DatabaseConnection
from utils.constants import COLLECTION_GROUPS
from utils.logger import get_logger

log = get_logger(__name__)


class GroupRepository:
    """Manages chat groups stored in MongoDB."""

    def __init__(self, db: DatabaseConnection) -> None:
        self.col: Collection = db.get_collection(COLLECTION_GROUPS)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.col.create_index("group_id", unique=True)
        self.col.create_index("members")

    # ── create ─────────────────────────────────────────────

    def create_group(
        self, group_name: str, creator: str, members: list[str]
    ) -> str:
        """Create a new group.  Returns the generated group_id."""
        group_id = str(uuid.uuid4())
        # Ensure creator is in members
        if creator not in members:
            members = [creator] + members
        self.col.insert_one(
            {
                "group_id": group_id,
                "group_name": group_name,
                "creator": creator,
                "members": members,
                "created_at": datetime.now(TZ_UTC7),
                "updated_at": datetime.now(TZ_UTC7),
            }
        )
        log.info("Group created: %s (%s) by %s", group_name, group_id, creator)
        return group_id

    # ── read ───────────────────────────────────────────────

    def get_group(self, group_id: str) -> dict | None:
        return self.col.find_one({"group_id": group_id}, {"_id": 0})

    def get_user_groups(self, username: str) -> list[dict]:
        """Return all groups *username* belongs to."""
        return list(
            self.col.find({"members": username}, {"_id": 0}).sort("group_name", 1)
        )

    # ── update ─────────────────────────────────────────────

    def add_member(self, group_id: str, username: str) -> bool:
        result = self.col.update_one(
            {"group_id": group_id},
            {
                "$addToSet": {"members": username},
                "$set": {"updated_at": datetime.now(TZ_UTC7)},
            },
        )
        return result.modified_count > 0

    def remove_member(self, group_id: str, username: str) -> bool:
        result = self.col.update_one(
            {"group_id": group_id},
            {
                "$pull": {"members": username},
                "$set": {"updated_at": datetime.now(TZ_UTC7)},
            },
        )
        return result.modified_count > 0
