"""
Message repository – offline messages + chat history.
"""

import uuid
from datetime import datetime, timedelta
from utils.timezone import TZ_UTC7

from pymongo.collection import Collection

from database.db_connection import DatabaseConnection
from utils.constants import (
    COLLECTION_CHAT_HISTORY,
    COLLECTION_OFFLINE_MESSAGES,
    OFFLINE_MSG_TTL_DAYS,
)
from utils.logger import get_logger

log = get_logger(__name__)


class MessageRepository:
    """Handles offline message storage and chat history persistence."""

    def __init__(self, db: DatabaseConnection) -> None:
        self.offline: Collection = db.get_collection(COLLECTION_OFFLINE_MESSAGES)
        self.history: Collection = db.get_collection(COLLECTION_CHAT_HISTORY)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        # Offline messages
        self.offline.create_index("recipient")
        self.offline.create_index("group_id")
        self.offline.create_index("delivered")
        self.offline.create_index("ttl_expires", expireAfterSeconds=0)

        # Chat history
        self.history.create_index(
            [("owner", 1), ("sender", 1), ("recipient", 1), ("timestamp", -1)]
        )
        self.history.create_index([("owner", 1), ("group_id", 1), ("timestamp", -1)])

    # ── offline messages ───────────────────────────────────

    def store_offline_message(
        self,
        sender: str,
        recipient: str,
        content_encrypted: str,
        aes_key_encrypted: str,
        iv: str,
        signature: str = "",
        group_id: str | None = None,
        message_id: str | None = None,
    ) -> str:
        """Store a message for an offline peer.  Returns the message_id."""
        if not message_id:
            message_id = str(uuid.uuid4())
        self.offline.insert_one(
            {
                "message_id": message_id,
                "sender": sender,
                "recipient": recipient,
                "group_id": group_id,
                "content_encrypted": content_encrypted,
                "aes_key_encrypted": aes_key_encrypted,
                "iv": iv,
                "signature": signature,
                "content_type": "text",
                "timestamp": datetime.now(TZ_UTC7),
                "delivered": False,
                "delivered_at": None,
                "ttl_expires": datetime.now(TZ_UTC7)
                + timedelta(days=OFFLINE_MSG_TTL_DAYS),
            }
        )
        log.info("Offline message stored: %s → %s  id=%s", sender, recipient, message_id)
        return message_id

    def get_offline_messages(self, username: str) -> list[dict]:
        """Return all undelivered messages for *username*."""
        return list(
            self.offline.find(
                {"recipient": username, "delivered": False},
                {"_id": 0},
            ).sort("timestamp", 1)
        )

    def mark_delivered(self, message_ids: list[str]) -> int:
        """Mark messages as delivered.  Returns count modified."""
        if not message_ids:
            return 0
        result = self.offline.update_many(
            {"message_id": {"$in": message_ids}},
            {
                "$set": {
                    "delivered": True,
                    "delivered_at": datetime.now(TZ_UTC7),
                }
            },
        )
        return result.modified_count

    # ── chat history ───────────────────────────────────────

    def save_to_history(
        self,
        message_id: str,
        sender: str,
        recipient: str | None,
        group_id: str | None,
        content_encrypted: str,
        aes_key_encrypted: str,
        iv: str,
        signature: str = "",
        message_type: str = "direct",
        owner: str = "",
    ) -> None:
        """Persist a message in the permanent chat history."""
        self.history.insert_one(
            {
                "message_id": message_id,
                "owner": owner,
                "sender": sender,
                "recipient": recipient,
                "group_id": group_id,
                "content_encrypted": content_encrypted,
                "aes_key_encrypted": aes_key_encrypted,
                "iv": iv,
                "signature": signature,
                "timestamp": datetime.now(TZ_UTC7),
                "message_type": message_type,
            }
        )

    def get_chat_history(
        self, user1: str, user2: str, limit: int = 50, skip: int = 0, owner: str = ""
    ) -> list[dict]:
        """Return direct-chat history between two users (newest last)."""
        cursor = (
            self.history.find(
                {
                    "owner": owner,
                    "$or": [
                        {"sender": user1, "recipient": user2},
                        {"sender": user2, "recipient": user1},
                    ],
                    "message_type": "direct",
                },
                {"_id": 0},
            )
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        messages = list(cursor)
        messages.reverse()  # oldest first
        return messages

    def get_group_history(
        self, group_id: str, limit: int = 50, skip: int = 0, owner: str = ""
    ) -> list[dict]:
        """Return group-chat history (newest last)."""
        cursor = (
            self.history.find(
                {"group_id": group_id, "message_type": "group", "owner": owner},
                {"_id": 0},
            )
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        messages = list(cursor)
        messages.reverse()
        return messages
