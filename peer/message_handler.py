"""
Message handler – routes incoming messages to the correct handler
and emits callbacks so the GUI can update.
"""

import asyncio
from typing import Callable, Optional

from crypto.encryption import E2EEncryption
from network.protocol import Protocol
from utils.constants import (
    MSG_CHAT_ACK,
    MSG_CHAT_MESSAGE,
    MSG_CREATE_GROUP_ACK,
    MSG_GROUP_ACK,
    MSG_GROUP_INVITE,
    MSG_GROUP_MESSAGE,
    MSG_GROUPS_LIST,
    MSG_GROUP_MEMBER_ADDED,
    MSG_GROUP_MEMBER_REMOVED,
    MSG_HEARTBEAT_ACK,
    MSG_KEY_EXCHANGE,
    MSG_KEY_EXCHANGE_ACK,
    MSG_LOGIN_ACK,
    MSG_PEER_UPDATE,
    MSG_PEERS_LIST,
    MSG_REGISTER_ACK,
    MSG_TYPING,
)
from utils.logger import get_logger

log = get_logger(__name__)


class MessageHandler:
    """
    Central message dispatcher.

    Callbacks (set by GUI or tests):
        on_message_received(sender, content, timestamp, msg_type, group_id)
        on_peer_update(action, peer_info_dict)
        on_group_invite(group_id, group_name, invited_by, members)
        on_groups_list(groups)
        on_typing(sender)
    """

    def __init__(self, peer_node) -> None:
        self.peer_node = peer_node

        # Callbacks (set externally by GUI)
        self.on_message_received: Optional[Callable] = None
        self.on_peer_update: Optional[Callable] = None
        self.on_group_invite: Optional[Callable] = None
        self.on_groups_list: Optional[Callable] = None
        self.on_group_member_added: Optional[Callable] = None
        self.on_group_member_removed: Optional[Callable] = None
        self.on_typing: Optional[Callable] = None
        self.on_auth_response: Optional[Callable] = None

    async def process(self, msg: dict, writer=None) -> None:
        """Parse message type and route to the appropriate handler."""
        msg_type = msg.get("type")
        log.debug("Processing message type: %s", msg_type)

        handler_map = {
            MSG_CHAT_MESSAGE: self._handle_chat_message,
            MSG_CHAT_ACK: self._handle_chat_ack,
            MSG_GROUP_MESSAGE: self._handle_group_message,
            MSG_GROUP_ACK: self._handle_group_ack,
            MSG_KEY_EXCHANGE: self._handle_key_exchange,
            MSG_KEY_EXCHANGE_ACK: self._handle_key_exchange_ack,
            MSG_PEER_UPDATE: self._handle_peer_update,
            MSG_PEERS_LIST: self._handle_peers_list,
            MSG_GROUP_INVITE: self._handle_group_invite,
            MSG_GROUPS_LIST: self._handle_groups_list,
            MSG_GROUP_MEMBER_ADDED: self._handle_group_member_added,
            MSG_GROUP_MEMBER_REMOVED: self._handle_group_member_removed,
            MSG_REGISTER_ACK: self._handle_auth_response,
            MSG_LOGIN_ACK: self._handle_auth_response,
            MSG_TYPING: self._handle_typing,
            MSG_HEARTBEAT_ACK: self._handle_heartbeat_ack,
        }

        handler = handler_map.get(msg_type)
        if handler:
            await handler(msg, writer)
        else:
            log.warning("No handler for message type: %s", msg_type)

    # ── chat messages ──────────────────────────────────────

    async def _handle_chat_message(self, msg: dict, writer) -> None:
        """Decrypt and process a direct chat message, then send ACK."""
        sender = msg["sender"]
        message_id = msg["message_id"]

        # Check for duplicates
        if hasattr(self.peer_node, "processed_messages"):
            if message_id in self.peer_node.processed_messages:
                log.debug("Duplicate chat message %s from %s", message_id, sender)
                # Send ACK to stop retry
                if msg.get("offline"):
                    return
                ack = {
                    "type": MSG_CHAT_ACK,
                    "message_id": message_id,
                    "status": "received",
                }
                if writer:
                    try:
                        await Protocol.send_message(writer, ack)
                    except Exception:
                        pass
                else:
                    await self.peer_node.peer_client.send(sender, ack)
                return
            self.peer_node.processed_messages.add(message_id)

        # Verify signature before decrypting
        signature = msg.get("signature")
        pub_key = self.peer_node.key_manager.get_peer_public_key(sender)
        
        if not signature or not pub_key:
            log.error("Missing signature or public key for sender %s", sender)
            plaintext = "[Verification failed: Missing signature or key]"
        elif not E2EEncryption.verify_signature(msg["content_encrypted"], signature, pub_key):
            log.error("Signature verification failed for message from %s", sender)
            plaintext = "[Verification failed: Invalid signature]"
        else:
            # Decrypt
            try:
                plaintext = E2EEncryption.decrypt_message(
                    msg["content_encrypted"],
                    msg["aes_key_encrypted"],
                    msg["iv"],
                    self.peer_node.key_manager.private_key,
                )
            except Exception as exc:
                log.error("Failed to decrypt message from %s: %s", sender, exc)
                plaintext = "[Decryption failed]"

        # Save to history
        try:
            await asyncio.to_thread(
                self.peer_node.message_repo.save_to_history,
                message_id=message_id,
                sender=sender,
                recipient=self.peer_node.username,
                group_id=None,
                content_encrypted=msg["content_encrypted"],
                aes_key_encrypted=msg["aes_key_encrypted"],
                iv=msg["iv"],
                signature=msg.get("signature", ""),
                message_type="direct",
                owner=self.peer_node.username,
            )
        except Exception as exc:
            log.error("Failed to save message to history: %s", exc)

        # Notify GUI
        if self.on_message_received:
            self.on_message_received(
                sender, plaintext, msg.get("timestamp", ""), "direct", None, message_id
            )

        # Send ACK
        if msg.get("offline"):
            log.debug("Offline message received – no ACK required")
            return

        if writer:
            try:
                await Protocol.send_message(
                    writer,
                    {
                        "type": MSG_CHAT_ACK,
                        "message_id": message_id,
                        "status": "received",
                    },
                )
            except Exception:
                pass
        else:
            # ACK via peer_client connection
            await self.peer_node.peer_client.send(
                sender,
                {
                    "type": MSG_CHAT_ACK,
                    "message_id": message_id,
                    "status": "received",
                },
            )

    async def _handle_chat_ack(self, msg: dict, writer) -> None:
        """Resolve the pending ACK event for the message."""
        message_id = msg.get("message_id")
        if message_id and message_id in self.peer_node.pending_acks:
            self.peer_node.pending_acks[message_id].set()
            log.debug("ACK received for message %s", message_id)

    # ── group messages ─────────────────────────────────────

    async def _handle_group_message(self, msg: dict, writer) -> None:
        sender = msg["sender"]
        message_id = msg["message_id"]
        group_id = msg["group_id"]

        # Check for duplicates
        if hasattr(self.peer_node, "processed_messages"):
            if message_id in self.peer_node.processed_messages:
                log.debug("Duplicate group message %s from %s", message_id, sender)
                # Send ACK to stop retry
                if msg.get("offline"):
                    return
                ack = {
                    "type": MSG_GROUP_ACK,
                    "message_id": message_id,
                    "group_id": group_id,
                    "status": "received",
                }
                if writer:
                    try:
                        await Protocol.send_message(writer, ack)
                    except Exception:
                        pass
                else:
                    await self.peer_node.peer_client.send(sender, ack)
                return
            self.peer_node.processed_messages.add(message_id)

        signature = msg.get("signature")
        pub_key = self.peer_node.key_manager.get_peer_public_key(sender)

        if not signature or not pub_key:
            log.error("Missing signature or public key for group message from %s", sender)
            plaintext = "[Verification failed: Missing signature or key]"
        elif not E2EEncryption.verify_signature(msg["content_encrypted"], signature, pub_key):
            log.error("Signature verification failed for group message from %s", sender)
            plaintext = "[Verification failed: Invalid signature]"
        else:
            try:
                plaintext = E2EEncryption.decrypt_message(
                    msg["content_encrypted"],
                    msg["aes_key_encrypted"],
                    msg["iv"],
                    self.peer_node.key_manager.private_key,
                )
            except Exception as exc:
                log.error("Failed to decrypt group message: %s", exc)
                plaintext = "[Decryption failed]"

        # Save to history
        try:
            await asyncio.to_thread(
                self.peer_node.message_repo.save_to_history,
                message_id=message_id,
                sender=sender,
                recipient=None,
                group_id=group_id,
                content_encrypted=msg["content_encrypted"],
                aes_key_encrypted=msg["aes_key_encrypted"],
                iv=msg["iv"],
                signature=msg.get("signature", ""),
                message_type="group",
                owner=self.peer_node.username,
            )
        except Exception as exc:
            log.error("Failed to save group message to history: %s", exc)

        if self.on_message_received:
            self.on_message_received(
                sender, plaintext, msg.get("timestamp", ""), "group", group_id, message_id
            )

        # Send ACK
        if msg.get("offline"):
            log.debug("Offline group message received – no ACK required")
            return

        ack = {
            "type": MSG_GROUP_ACK,
            "message_id": message_id,
            "group_id": group_id,
            "status": "received",
        }
        if writer:
            try:
                await Protocol.send_message(writer, ack)
            except Exception:
                pass
        else:
            await self.peer_node.peer_client.send(sender, ack)

    async def _handle_group_ack(self, msg: dict, writer) -> None:
        message_id = msg.get("message_id")
        if message_id and message_id in self.peer_node.pending_acks:
            self.peer_node.pending_acks[message_id].set()

    # ── key exchange ───────────────────────────────────────

    async def _handle_key_exchange(self, msg: dict, writer) -> None:
        """Store peer's public key and reply with our own."""
        username = msg["username"]
        public_key_pem = msg["public_key"]
        self.peer_node.key_manager.add_peer_public_key(username, public_key_pem)

        if writer:
            await Protocol.send_message(
                writer,
                {
                    "type": MSG_KEY_EXCHANGE_ACK,
                    "username": self.peer_node.username,
                    "public_key": self.peer_node.key_manager.get_public_key_pem(),
                },
            )

    async def _handle_key_exchange_ack(self, msg: dict, writer) -> None:
        username = msg["username"]
        public_key_pem = msg["public_key"]
        self.peer_node.key_manager.add_peer_public_key(username, public_key_pem)

    # ── peer updates ───────────────────────────────────────

    async def _handle_peer_update(self, msg: dict, writer) -> None:
        action = msg["action"]
        peer_info = msg["peer"]
        username = peer_info["username"]

        if action == "joined":
            self.peer_node.known_peers[username] = peer_info
            # Cache their public key
            if peer_info.get("public_key"):
                self.peer_node.key_manager.add_peer_public_key(
                    username, peer_info["public_key"]
                )
        elif action == "left":
            self.peer_node.known_peers.pop(username, None)

        if self.on_peer_update:
            self.on_peer_update(action, peer_info)

    async def _handle_peers_list(self, msg: dict, writer) -> None:
        for p in msg.get("peers", []):
            username = p["username"]
            is_new = username not in self.peer_node.known_peers
            self.peer_node.known_peers[username] = p
            if p.get("public_key"):
                self.peer_node.key_manager.add_peer_public_key(
                    username, p["public_key"]
                )
            # Emit peer update for the UI so that any missing peers appear
            if is_new and self.on_peer_update:
                self.on_peer_update("joined", p)

    # ── groups ─────────────────────────────────────────────

    def _extract_and_cache_group_keys(self, members_data: list) -> list[str]:
        """Extract public keys from members list, cache them, and return usernames."""
        usernames = []
        for m in members_data:
            if isinstance(m, dict):
                username = m.get("username")
                pub_key = m.get("public_key")
                usernames.append(username)
                if username and pub_key:
                    self.peer_node.key_manager.add_peer_public_key(username, pub_key)
            else:
                usernames.append(m)
        return usernames

    async def _handle_group_invite(self, msg: dict, writer) -> None:
        group_id = msg["group_id"]
        group_name = msg["group_name"]
        invited_by = msg["invited_by"]
        members = self._extract_and_cache_group_keys(msg.get("members", []))

        # Cache group locally
        self.peer_node.groups[group_id] = {
            "group_id": group_id,
            "group_name": group_name,
            "members": members,
        }

        if self.on_group_invite:
            self.on_group_invite(group_id, group_name, invited_by, members)

    async def _handle_groups_list(self, msg: dict, writer) -> None:
        groups = msg.get("groups", [])
        for g in groups:
            g["members"] = self._extract_and_cache_group_keys(g.get("members", []))
            self.peer_node.groups[g["group_id"]] = g
        if self.on_groups_list:
            self.on_groups_list(groups)

    async def _handle_group_member_added(self, msg: dict, writer) -> None:
        group_id = msg["group_id"]
        group_name = msg["group_name"]
        new_member = msg["new_member"]
        added_by = msg["added_by"]
        members = self._extract_and_cache_group_keys(msg.get("members", []))

        if group_id in self.peer_node.groups:
            self.peer_node.groups[group_id]["members"] = members
        
        if self.on_group_member_added:
            self.on_group_member_added(group_id, group_name, new_member, added_by, members)

    async def _handle_group_member_removed(self, msg: dict, writer) -> None:
        group_id = msg["group_id"]
        group_name = msg["group_name"]
        removed_member = msg["removed_member"]
        removed_by = msg["removed_by"]
        members = self._extract_and_cache_group_keys(msg.get("members", []))

        # If I am the one removed, remove the group from my list
        if removed_member == self.peer_node.username:
            self.peer_node.groups.pop(group_id, None)
        elif group_id in self.peer_node.groups:
            self.peer_node.groups[group_id]["members"] = members
            
        if self.on_group_member_removed:
            self.on_group_member_removed(group_id, group_name, removed_member, removed_by, members)

    # ── auth ───────────────────────────────────────────────

    async def _handle_auth_response(self, msg: dict, writer) -> None:
        """Handle REGISTER_ACK / LOGIN_ACK from bootstrap server."""
        if msg.get("status") == "success":
            # Populate known peers + keys
            for p in msg.get("peers", []):
                self.peer_node.known_peers[p["username"]] = p
                if p.get("public_key"):
                    self.peer_node.key_manager.add_peer_public_key(
                        p["username"], p["public_key"]
                    )
        if self.on_auth_response:
            self.on_auth_response(msg)

    # ── typing ─────────────────────────────────────────────

    async def _handle_typing(self, msg: dict, writer) -> None:
        if self.on_typing:
            self.on_typing(msg.get("sender", ""))

    # ── heartbeat ──────────────────────────────────────────

    async def _handle_heartbeat_ack(self, msg: dict, writer) -> None:
        """Handle HEARTBEAT_ACK from bootstrap server."""
        log.debug("Heartbeat acknowledged by bootstrap server: %s", msg.get("status"))
