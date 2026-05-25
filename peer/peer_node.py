"""
Peer node – the main class that combines client, server, and message handling.

Each peer node:
    * Connects to the bootstrap server for discovery
    * Runs a local TCP server to accept incoming peer connections
    * Opens TCP connections to other peers for direct messaging
    * Handles E2E encryption, reliable delivery, and offline messaging
"""

import asyncio
import uuid
from datetime import datetime
from utils.timezone import TZ_UTC7
from typing import Optional

from crypto.encryption import E2EEncryption
from crypto.key_manager import KeyManager
from database.db_connection import DatabaseConnection
from database.group_repository import GroupRepository
from database.message_repository import MessageRepository
from network.connection import PeerInfo
from network.protocol import Protocol
from peer.message_handler import MessageHandler
from peer.peer_client import PeerClient
from peer.peer_server import PeerServer
from utils.constants import (
    ACK_TIMEOUT,
    MAX_RETRIES,
    MSG_CHAT_MESSAGE,
    MSG_CREATE_GROUP,
    MSG_DISCONNECT,
    MSG_GET_GROUPS,
    MSG_GET_PEERS,
    MSG_GROUP_MESSAGE,
    MSG_HEARTBEAT,
    MSG_KEY_EXCHANGE,
    MSG_LOGIN,
    MSG_REGISTER,
    MSG_TYPING,
    RETRY_BASE_DELAY,
    STATUS_SUCCESS,
    MSG_ADD_GROUP_MEMBER,
    MSG_REMOVE_GROUP_MEMBER,
    MSG_STORE_OFFLINE,
)
from utils.config import Config
from utils.logger import get_logger

log = get_logger(__name__)


class PeerNode:
    """
    The main P2P peer – combines all subsystems.
    """

    def __init__(self, username: str, host: str, port: int, db: DatabaseConnection) -> None:
        self.username = username
        self.host = host
        self.port = port
        self.db = db

        # Sub-components
        self.key_manager = KeyManager(username)
        self.peer_server = PeerServer(host, port, self)
        self.peer_client = PeerClient(self)
        self.message_handler = MessageHandler(self)

        # Repositories
        self.message_repo = MessageRepository(db)
        self.group_repo = GroupRepository(db)

        # State
        self.known_peers: dict[str, dict] = {}    # {username: peer_info_dict}
        self.groups: dict[str, dict] = {}           # {group_id: group_info}
        self.pending_acks: dict[str, asyncio.Event] = {}
        self.processed_messages: set[str] = set()

        # Bootstrap connection
        self._bs_reader: Optional[asyncio.StreamReader] = None
        self._bs_writer: Optional[asyncio.StreamWriter] = None
        self._bs_read_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    # ── lifecycle ──────────────────────────────────────────

    async def start(self) -> None:
        """Start the peer server (for incoming P2P connections)."""
        self.key_manager.load_or_generate()
        await self.peer_server.start()
        self._running = True
        log.info("PeerNode started: %s @ %s:%d", self.username, self.host, self.port)

    async def connect_to_bootstrap(self, bs_host: str, bs_port: int) -> bool:
        """Establish a persistent connection to the bootstrap server."""
        try:
            self._bs_reader, self._bs_writer = await asyncio.open_connection(
                bs_host, bs_port
            )
            # Background reader for bootstrap messages
            self._bs_read_task = asyncio.ensure_future(self._bootstrap_read_loop())
            log.info("Connected to bootstrap server %s:%d", bs_host, bs_port)
            return True
        except (ConnectionRefusedError, OSError) as exc:
            log.error("Cannot connect to bootstrap: %s", exc)
            return False

    async def register(self, password: str) -> asyncio.Future:
        """Register a new account via bootstrap."""
        auth_future = asyncio.get_event_loop().create_future()

        def on_response(msg):
            if not auth_future.done():
                auth_future.set_result(msg)

        self.message_handler.on_auth_response = on_response

        await Protocol.send_message(
            self._bs_writer,
            {
                "type": MSG_REGISTER,
                "username": self.username,
                "password": password,
                "host": self.host,
                "port": self.port,
                "public_key": self.key_manager.get_public_key_pem(),
                "timestamp": datetime.now(TZ_UTC7).isoformat(),
            },
        )

        try:
            result = await asyncio.wait_for(auth_future, timeout=10)
            if result.get("status") == STATUS_SUCCESS:
                self._start_heartbeat()
                await self._request_groups()
            return result
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Registration timeout"}

    async def login(self, password: str) -> dict:
        """Log in via bootstrap."""
        auth_future = asyncio.get_event_loop().create_future()

        def on_response(msg):
            if not auth_future.done():
                auth_future.set_result(msg)

        self.message_handler.on_auth_response = on_response

        await Protocol.send_message(
            self._bs_writer,
            {
                "type": MSG_LOGIN,
                "username": self.username,
                "password": password,
                "host": self.host,
                "port": self.port,
                "public_key": self.key_manager.get_public_key_pem(),
            },
        )

        try:
            result = await asyncio.wait_for(auth_future, timeout=10)
            if result.get("status") == STATUS_SUCCESS:
                self._start_heartbeat()
                await self._request_groups()
            return result
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Login timeout"}

    async def disconnect(self) -> None:
        """Graceful shutdown."""
        self._running = False

        # Notify bootstrap
        if self._bs_writer and not self._bs_writer.is_closing():
            try:
                await Protocol.send_message(
                    self._bs_writer,
                    {"type": MSG_DISCONNECT, "username": self.username},
                )
                self._bs_writer.close()
            except Exception:
                pass

        # Cancel tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._bs_read_task:
            self._bs_read_task.cancel()

        # Disconnect peers
        await self.peer_client.disconnect_all()
        await self.peer_server.stop()
        log.info("PeerNode %s disconnected", self.username)

    # ── messaging ──────────────────────────────────────────

    async def send_message(self, recipient: str, content: str) -> bool:
        """
        Send an E2E-encrypted direct message to *recipient*.
        Returns True if ACK received, False if stored offline.
        """
        # Get recipient public key
        pub_key = self.key_manager.get_peer_public_key(recipient)
        if pub_key is None:
            log.warning("No public key for %s – cannot encrypt", recipient)
            return False

        # Encrypt
        encrypted = E2EEncryption.encrypt_message(content, pub_key)
        message_id = str(uuid.uuid4())
        signature = E2EEncryption.sign_message(encrypted["content_encrypted"], self.key_manager.private_key)

        msg = {
            "type": MSG_CHAT_MESSAGE,
            "message_id": message_id,
            "sender": self.username,
            "recipient": recipient,
            "content_encrypted": encrypted["content_encrypted"],
            "aes_key_encrypted": encrypted["aes_key_encrypted"],
            "iv": encrypted["iv"],
            "signature": signature,
            "timestamp": datetime.now(TZ_UTC7).isoformat(),
        }

        # Save to own history (use sender's own key)
        own_pub_key = self.key_manager.public_key
        own_encrypted = E2EEncryption.encrypt_message(content, own_pub_key)
        own_signature = E2EEncryption.sign_message(own_encrypted["content_encrypted"], self.key_manager.private_key)

        try:
            await asyncio.to_thread(
                self.message_repo.save_to_history,
                message_id=message_id,
                sender=self.username,
                recipient=recipient,
                group_id=None,
                content_encrypted=own_encrypted["content_encrypted"],
                aes_key_encrypted=own_encrypted["aes_key_encrypted"],
                iv=own_encrypted["iv"],
                signature=own_signature,
                message_type="direct",
                owner=self.username,
            )
        except Exception as exc:
            log.error("Failed to save message to history: %s", exc)

        # Try to connect & send with reliable delivery
        connected = await self._ensure_peer_connection(recipient)
        if not connected:
            # Store offline
            await self._store_offline(recipient, encrypted, signature, message_id)
            return False

        # Send with ACK/retry
        delivered = await self._send_with_retry(recipient, msg, message_id)
        if not delivered:
            await self._store_offline(recipient, encrypted, signature, message_id)
        return delivered

    async def send_group_message(self, group_id: str, content: str) -> None:
        """Send an encrypted message to all group members."""
        group = self.groups.get(group_id)
        if not group:
            log.warning("Unknown group: %s", group_id)
            return

        message_id = str(uuid.uuid4())
        members = group["members"]

        for member in members:
            if member == self.username:
                continue

            pub_key = self.key_manager.get_peer_public_key(member)
            if pub_key is None:
                log.warning("No public key for group member %s", member)
                continue

            encrypted = E2EEncryption.encrypt_message(content, pub_key)
            signature = E2EEncryption.sign_message(encrypted["content_encrypted"], self.key_manager.private_key)

            msg = {
                "type": MSG_GROUP_MESSAGE,
                "message_id": f"{message_id}_{member}",
                "sender": self.username,
                "group_id": group_id,
                "content_encrypted": encrypted["content_encrypted"],
                "aes_key_encrypted": encrypted["aes_key_encrypted"],
                "iv": encrypted["iv"],
                "signature": signature,
                "timestamp": datetime.now(TZ_UTC7).isoformat(),
            }

            connected = await self._ensure_peer_connection(member)
            if connected:
                # Use _send_with_retry for reliable delivery with ACK
                delivered = await self._send_with_retry(member, msg, msg["message_id"])
                if not delivered:
                    await self._store_offline(member, encrypted, signature, msg["message_id"], group_id)
            else:
                # Offline -> store on bootstrap
                await self._store_offline(member, encrypted, signature, msg["message_id"], group_id)

        # Save one copy to own history (use sender's own key)
        own_pub_key = self.key_manager.public_key
        own_encrypted = E2EEncryption.encrypt_message(content, own_pub_key)
        own_signature = E2EEncryption.sign_message(own_encrypted["content_encrypted"], self.key_manager.private_key)

        try:
            await asyncio.to_thread(
                self.message_repo.save_to_history,
                message_id=message_id,
                sender=self.username,
                recipient=None,
                group_id=group_id,
                content_encrypted=own_encrypted["content_encrypted"],
                aes_key_encrypted=own_encrypted["aes_key_encrypted"],
                iv=own_encrypted["iv"],
                signature=own_signature,
                message_type="group",
                owner=self.username,
            )
        except Exception as exc:
            log.error("Failed to save group message to history: %s", exc)

    async def create_group(self, group_name: str, members: list[str]) -> dict | None:
        """Request group creation from bootstrap server."""
        if not self._bs_writer:
            return None

        result_future = asyncio.get_event_loop().create_future()

        original_callback = self.message_handler.on_group_invite

        def on_create_ack(msg):
            # CREATE_GROUP_ACK comes through the auth handler path
            pass

        # We'll listen for CREATE_GROUP_ACK through a temporary handler
        saved_process = None

        async def temp_group_handler(msg, writer):
            if msg.get("type") == "CREATE_GROUP_ACK" and not result_future.done():
                result_future.set_result(msg)
            else:
                await self.message_handler.process(msg, writer)

        await Protocol.send_message(
            self._bs_writer,
            {
                "type": MSG_CREATE_GROUP,
                "group_name": group_name,
                "creator": self.username,
                "members": members if self.username in members else [self.username] + members,
            },
        )

        # Wait for ACK (it will arrive via bootstrap read loop)
        try:
            # The response will be caught by the bootstrap read loop
            # We need a different approach: use an event
            create_event = asyncio.Event()
            created_group = {}

            orig_process = self.message_handler.process

            async def patched_process(msg, writer=None):
                if msg.get("type") == "CREATE_GROUP_ACK":
                    created_group.update(msg)
                    create_event.set()
                else:
                    await orig_process(msg, writer)

            self.message_handler.process = patched_process
            await asyncio.wait_for(create_event.wait(), timeout=10)
            self.message_handler.process = orig_process

            if created_group.get("status") == STATUS_SUCCESS:
                gid = created_group["group_id"]
                members = self.message_handler._extract_and_cache_group_keys(created_group.get("members", []))
                self.groups[gid] = {
                    "group_id": gid,
                    "group_name": created_group["group_name"],
                    "members": members,
                }
                created_group["members"] = members
                return created_group
            return None
        except asyncio.TimeoutError:
            self.message_handler.process = orig_process
            return None

    async def add_group_member(self, group_id: str, username: str) -> None:
        if self._bs_writer:
            await Protocol.send_message(
                self._bs_writer,
                {
                    "type": MSG_ADD_GROUP_MEMBER,
                    "group_id": group_id,
                    "new_member": username,
                    "username": self.username,
                },
            )

    async def remove_group_member(self, group_id: str, username: str) -> None:
        if self._bs_writer:
            await Protocol.send_message(
                self._bs_writer,
                {
                    "type": MSG_REMOVE_GROUP_MEMBER,
                    "group_id": group_id,
                    "member_to_remove": username,
                    "username": self.username,
                },
            )

    async def send_typing(self, recipient: str) -> None:
        """Notify a peer that we are typing."""
        await self.peer_client.send(
            recipient,
            {"type": MSG_TYPING, "sender": self.username, "recipient": recipient},
        )

    async def refresh_peers(self) -> None:
        """Request updated peer list from bootstrap."""
        if self._bs_writer:
            await Protocol.send_message(
                self._bs_writer,
                {"type": MSG_GET_PEERS, "username": self.username},
            )

    # ── internal helpers ───────────────────────────────────

    async def _ensure_peer_connection(self, username: str) -> bool:
        """Make sure we have a direct TCP connection to *username*."""
        if await self.peer_client.is_connected(username):
            return True
        peer_info_dict = self.known_peers.get(username)
        if not peer_info_dict:
            return False
        pi = PeerInfo(
            username=username,
            host=peer_info_dict["host"],
            port=peer_info_dict["port"],
            public_key=peer_info_dict.get("public_key", ""),
        )
        return await self.peer_client.connect(pi)

    async def _send_with_retry(
        self, recipient: str, msg: dict, message_id: str
    ) -> bool:
        """
        Send *msg* and wait for ACK with exponential-backoff retry.
        Returns True if ACK received.
        """
        event = asyncio.Event()
        self.pending_acks[message_id] = event

        for attempt in range(MAX_RETRIES + 1):
            sent = await self.peer_client.send(recipient, msg)
            if not sent:
                break

            try:
                await asyncio.wait_for(event.wait(), timeout=ACK_TIMEOUT)
                self.pending_acks.pop(message_id, None)
                return True
            except asyncio.TimeoutError:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                log.warning(
                    "No ACK for %s (attempt %d/%d), retrying in %ds …",
                    message_id,
                    attempt + 1,
                    MAX_RETRIES + 1,
                    delay,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(delay)

        self.pending_acks.pop(message_id, None)
        log.warning("Message %s: all retries exhausted → storing offline", message_id)
        return False

    async def _store_offline(
        self, recipient: str, encrypted: dict, signature: str, message_id: str, group_id: str | None = None
    ) -> None:
        """Send an undelivered message to Bootstrap Server for offline storage."""
        if not self._bs_writer:
            return
            
        try:
            await Protocol.send_message(
                self._bs_writer,
                {
                    "type": MSG_STORE_OFFLINE,
                    "sender": self.username,
                    "recipient": recipient,
                    "content_encrypted": encrypted["content_encrypted"],
                    "aes_key_encrypted": encrypted["aes_key_encrypted"],
                    "iv": encrypted["iv"],
                    "signature": signature,
                    "group_id": group_id,
                    "message_id": message_id,
                }
            )
        except Exception as exc:
            log.warning("Failed to send offline msg to Bootstrap Server: %s", exc)

    def _start_heartbeat(self) -> None:
        """Begin periodic heartbeat to bootstrap."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Periodically send a heartbeat to the bootstrap server and sync peers."""
        try:
            while self._running:
                await asyncio.sleep(Config.HEARTBEAT_INTERVAL)
                if self._bs_writer:
                    # Send heartbeat
                    try:
                        await Protocol.send_message(
                            self._bs_writer,
                            {
                                "type": MSG_HEARTBEAT,
                                "username": self.username,
                                "timestamp": datetime.now(TZ_UTC7).isoformat(),
                            },
                        )
                        # Sync peer list in case we missed a broadcast
                        await self.refresh_peers()
                    except Exception as exc:
                        log.debug("Heartbeat/refresh failed: %s", exc)
        except asyncio.CancelledError:
            pass

    async def _bootstrap_read_loop(self) -> None:
        """Read messages from the bootstrap server."""
        try:
            while self._running:
                try:
                    msg = await Protocol.receive_message(self._bs_reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    log.warning("Bootstrap connection lost")
                    break
                if msg is None:
                    break
                await self.message_handler.process(msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("Bootstrap read loop error: %s", exc)

    async def _request_groups(self) -> None:
        """Fetch groups from bootstrap after login."""
        if self._bs_writer:
            await Protocol.send_message(
                self._bs_writer,
                {"type": MSG_GET_GROUPS, "username": self.username},
            )

    # ── chat history ───────────────────────────────────────

    async def get_chat_history(
        self, peer_username: str, limit: int = 50, skip: int = 0
    ) -> list[dict]:
        """Fetch chat history with a peer (runs in background)."""
        raw = await asyncio.to_thread(
            self.message_repo.get_chat_history,
            self.username,
            peer_username,
            limit,
            skip,
            self.username,
        )
        result = []
        for m in raw:
            try:
                plaintext = E2EEncryption.decrypt_message(
                    m["content_encrypted"],
                    m["aes_key_encrypted"],
                    m["iv"],
                    self.key_manager.private_key,
                )
            except Exception:
                plaintext = "[Cannot decrypt – key mismatch]"
            result.append(
                {
                    "sender": m["sender"],
                    "content": plaintext,
                    "timestamp": m.get("timestamp", ""),
                    "message_id": m.get("message_id", ""),
                }
            )
        return result

    async def get_group_history(
        self, group_id: str, limit: int = 50, skip: int = 0
    ) -> list[dict]:
        """Fetch group chat history (runs in background)."""
        raw = await asyncio.to_thread(
            self.message_repo.get_group_history, group_id, limit, skip, self.username
        )
        result = []
        for m in raw:
            try:
                plaintext = E2EEncryption.decrypt_message(
                    m["content_encrypted"],
                    m["aes_key_encrypted"],
                    m["iv"],
                    self.key_manager.private_key,
                )
            except Exception:
                plaintext = "[Cannot decrypt]"
            result.append(
                {
                    "sender": m["sender"],
                    "content": plaintext,
                    "timestamp": m.get("timestamp", ""),
                    "message_id": m.get("message_id", ""),
                }
            )
        return result
