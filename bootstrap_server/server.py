"""
Bootstrap / Tracker server.

Responsibilities:
    * Accept peer connections (REGISTER / LOGIN)
    * Maintain a live registry of online peers
    * Broadcast PEER_UPDATE when peers join or leave
    * Monitor heartbeats and evict dead peers
    * Deliver offline messages when a peer comes online
    * Manage groups (CREATE_GROUP, GET_GROUPS)
"""

import asyncio
from datetime import datetime, timezone

from bootstrap_server.heartbeat_monitor import HeartbeatMonitor
from bootstrap_server.peer_registry import PeerRegistry, RegisteredPeer
from database.db_connection import DatabaseConnection
from database.group_repository import GroupRepository
from database.message_repository import MessageRepository
from database.user_repository import UserRepository
from network.protocol import Protocol
from utils.constants import (
    ACTION_JOINED,
    ACTION_LEFT,
    MSG_CHAT_MESSAGE,
    MSG_GROUP_MESSAGE,
    MSG_CREATE_GROUP,
    MSG_CREATE_GROUP_ACK,
    MSG_DISCONNECT,
    MSG_GET_GROUPS,
    MSG_GET_PEERS,
    MSG_GROUP_INVITE,
    MSG_GROUPS_LIST,
    MSG_ADD_GROUP_MEMBER,
    MSG_REMOVE_GROUP_MEMBER,
    MSG_GROUP_MEMBER_ADDED,
    MSG_GROUP_MEMBER_REMOVED,
    MSG_HEARTBEAT,
    MSG_HEARTBEAT_ACK,
    MSG_LOGIN,
    MSG_LOGIN_ACK,
    MSG_PEER_UPDATE,
    MSG_PEERS_LIST,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_STORE_OFFLINE,
    STATUS_ERROR,
    STATUS_OFFLINE,
    STATUS_ONLINE,
    STATUS_SUCCESS,
)
from utils.logger import get_logger

log = get_logger(__name__)


class BootstrapServer:
    """Central coordination server for the P2P chat network."""

    def __init__(self, host: str, port: int, db: DatabaseConnection) -> None:
        self.host = host
        self.port = port
        self.db = db

        # Repositories
        self.user_repo = UserRepository(db)
        self.message_repo = MessageRepository(db)
        self.group_repo = GroupRepository(db)

        # Runtime
        self.registry = PeerRegistry()
        self.heartbeat = HeartbeatMonitor(self.registry)
        self.heartbeat.on_dead_peer = self._handle_dead_peer

        self._server: asyncio.AbstractServer | None = None
        self._running = False

    # ── lifecycle ──────────────────────────────────────────

    async def start(self) -> None:
        """Start listening for peer connections."""
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        self._running = True
        self.heartbeat.start()

        addr = self._server.sockets[0].getsockname()
        log.info("Bootstrap server listening on %s:%d", addr[0], addr[1])

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        self._running = False
        await self.heartbeat.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        log.info("Bootstrap server stopped")

    # ── client handler ─────────────────────────────────────

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle one peer connection for its entire lifetime."""
        peer_addr = writer.get_extra_info("peername")
        username: str | None = None
        log.info("New connection from %s", peer_addr)

        try:
            while self._running:
                try:
                    msg = await Protocol.receive_message(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                if msg is None:
                    break

                msg_type = msg.get("type")
                username_in_msg = msg.get("username", username)

                if msg_type == MSG_REGISTER:
                    username = await self._handle_register(msg, reader, writer)
                elif msg_type == MSG_LOGIN:
                    username = await self._handle_login(msg, reader, writer)
                elif msg_type == MSG_HEARTBEAT:
                    await self._handle_heartbeat(msg)
                elif msg_type == MSG_GET_PEERS:
                    await self._handle_get_peers(msg, writer)
                elif msg_type == MSG_DISCONNECT:
                    username = msg.get("username", username)
                    break
                elif msg_type == MSG_CREATE_GROUP:
                    await self._handle_create_group(msg, writer)
                elif msg_type == MSG_GET_GROUPS:
                    await self._handle_get_groups(msg, writer)
                elif msg_type == MSG_ADD_GROUP_MEMBER:
                    await self._handle_add_group_member(msg, writer)
                elif msg_type == MSG_REMOVE_GROUP_MEMBER:
                    await self._handle_remove_group_member(msg, writer)
                elif msg_type == MSG_STORE_OFFLINE:
                    await self._handle_store_offline(msg)
                else:
                    log.warning("Unknown message type: %s", msg_type)

        except Exception as exc:
            log.error("Error handling client %s: %s", peer_addr, exc)
        finally:
            if username:
                await self._peer_disconnected(username)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info("Connection closed: %s (user=%s)", peer_addr, username)

    # ── message handlers ───────────────────────────────────

    async def _handle_register(
        self,
        msg: dict,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> str | None:
        """Create a new user account and add to online registry."""
        username = msg["username"]
        password = msg["password"]
        host = msg["host"]
        port = msg["port"]
        public_key = msg.get("public_key", "")

        # 1. Register in Database
        ok = await asyncio.to_thread(self.user_repo.create_user, username, password, public_key)
        if not ok:
            await Protocol.send_message(
                writer,
                {
                    "type": MSG_REGISTER_ACK,
                    "status": STATUS_ERROR,
                    "message": "Username already exists",
                    "peers": [],
                },
            )
            return None

        # Register in live registry
        await self.registry.register(username, host, port, public_key, reader, writer)
        await asyncio.to_thread(self.user_repo.update_status, username, STATUS_ONLINE)
        await self.heartbeat.update(username)

        # Send ACK with peer list
        peers = await self.registry.get_peer_list_dicts(exclude=username)
        await Protocol.send_message(
            writer,
            {
                "type": MSG_REGISTER_ACK,
                "status": STATUS_SUCCESS,
                "message": "Registered successfully",
                "peers": peers,
            },
        )

        # Broadcast join
        await self._broadcast_peer_update(ACTION_JOINED, username, host, port, public_key)

        # Deliver offline messages
        await self._deliver_offline_messages(username, writer)

        return username

    async def _handle_login(
        self,
        msg: dict,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> str | None:
        """Authenticate an existing user and add to online registry."""
        username = msg["username"]
        password = msg["password"]
        host = msg["host"]
        port = msg["port"]
        public_key = msg.get("public_key", "")

        verified = await asyncio.to_thread(self.user_repo.verify_password, username, password)
        if not verified:
            await Protocol.send_message(
                writer,
                {
                    "type": MSG_LOGIN_ACK,
                    "status": STATUS_ERROR,
                    "message": "Invalid username or password",
                    "peers": [],
                },
            )
            return None

        # Update public key if changed
        await asyncio.to_thread(self.user_repo.update_public_key, username, public_key)

        # Register in live registry
        await self.registry.register(username, host, port, public_key, reader, writer)
        await asyncio.to_thread(self.user_repo.update_status, username, STATUS_ONLINE)
        await self.heartbeat.update(username)

        peers = await self.registry.get_peer_list_dicts(exclude=username)
        await Protocol.send_message(
            writer,
            {
                "type": MSG_LOGIN_ACK,
                "status": STATUS_SUCCESS,
                "message": "Login successful",
                "peers": peers,
            },
        )

        await self._broadcast_peer_update(ACTION_JOINED, username, host, port, public_key)
        await self._deliver_offline_messages(username, writer)

        return username

    async def _handle_heartbeat(self, msg: dict) -> None:
        username = msg.get("username", "")
        if username:
            await self.heartbeat.update(username)
            # Send ACK back through registry writer
            peer = await self.registry.get(username)
            if peer:
                try:
                    await Protocol.send_message(
                        peer.writer,
                        {"type": MSG_HEARTBEAT_ACK, "status": "alive"},
                    )
                except Exception:
                    pass

    async def _handle_get_peers(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        username = msg.get("username", "")
        peers = await self.registry.get_peer_list_dicts(exclude=username)
        await Protocol.send_message(
            writer, {"type": MSG_PEERS_LIST, "peers": peers}
        )

    async def _get_members_with_keys(self, members: list[str]) -> list[dict]:
        result = []
        for m in members:
            user = await asyncio.to_thread(self.user_repo.get_user, m)
            pub_key = user.get("public_key", "") if user else ""
            result.append({"username": m, "public_key": pub_key})
        return result

    async def _handle_create_group(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        group_name = msg["group_name"]
        creator = msg["creator"]
        members = msg["members"]

        group_id = await asyncio.to_thread(self.group_repo.create_group, group_name, creator, members)
        full_members = members if creator in members else [creator] + members
        members_with_keys = await self._get_members_with_keys(full_members)

        await Protocol.send_message(
            writer,
            {
                "type": MSG_CREATE_GROUP_ACK,
                "status": STATUS_SUCCESS,
                "group_id": group_id,
                "group_name": group_name,
                "members": members_with_keys,
            },
        )

        # Notify other members
        async def send_bg(writer, msg):
            try:
                await Protocol.send_message(writer, msg)
            except Exception:
                pass

        for member in members:
            if member == creator:
                continue
            peer = await self.registry.get(member)
            if peer:
                asyncio.create_task(send_bg(
                    peer.writer,
                    {
                        "type": MSG_GROUP_INVITE,
                        "group_id": group_id,
                        "group_name": group_name,
                        "invited_by": creator,
                        "members": members_with_keys,
                    }
                ))

    async def _handle_get_groups(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        username = msg["username"]
        groups = await asyncio.to_thread(self.group_repo.get_user_groups, username)
        # Convert datetime objects to string for JSON serialisation
        for g in groups:
            g["members"] = await self._get_members_with_keys(g["members"])
            for k in ("created_at", "updated_at"):
                if k in g and hasattr(g[k], "isoformat"):
                    g[k] = g[k].isoformat()
        await Protocol.send_message(
            writer, {"type": MSG_GROUPS_LIST, "groups": groups}
        )

    async def _handle_add_group_member(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        group_id = msg["group_id"]
        new_member = msg["new_member"]
        added_by = msg["username"]

        # 1. Update database
        await asyncio.to_thread(self.group_repo.add_member, group_id, new_member)
        
        # 2. Get full group info
        group_info = await asyncio.to_thread(self.group_repo.get_group, group_id)
        if not group_info:
            return
            
        members_with_keys = await self._get_members_with_keys(group_info["members"])

        # 3. Notify the new member (send them the full group via INVITE)
        peer = await self.registry.get(new_member)
        if peer:
            try:
                await Protocol.send_message(
                    peer.writer,
                    {
                        "type": MSG_GROUP_INVITE,
                        "group_id": group_id,
                        "group_name": group_info["group_name"],
                        "invited_by": added_by,
                        "members": members_with_keys,
                    },
                )
            except Exception:
                log.warning("Failed to notify %s about group addition", new_member)

        # 4. Notify existing members
        async def send_bg(writer, msg):
            try:
                await Protocol.send_message(writer, msg)
            except Exception:
                pass

        for member in group_info["members"]:
            if member == new_member:
                continue
            peer = await self.registry.get(member)
            if peer:
                asyncio.create_task(send_bg(
                    peer.writer,
                    {
                        "type": MSG_GROUP_MEMBER_ADDED,
                        "group_id": group_id,
                        "group_name": group_info["group_name"],
                        "new_member": new_member,
                        "added_by": added_by,
                        "members": members_with_keys,
                    }
                ))

    async def _handle_remove_group_member(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        group_id = msg["group_id"]
        member_to_remove = msg["member_to_remove"]
        removed_by = msg["username"]

        # 1. Update DB
        group_info = await asyncio.to_thread(self.group_repo.get_group, group_id)
        if not group_info or member_to_remove not in group_info.get("members", []):
            return

        await asyncio.to_thread(self.group_repo.remove_member, group_id, member_to_remove)

        # 2. Notify all members (including the one being removed)
        updated_members = [m for m in group_info["members"] if m != member_to_remove]
        members_with_keys = await self._get_members_with_keys(updated_members)
        async def send_bg(writer, msg):
            try:
                await Protocol.send_message(writer, msg)
            except Exception:
                pass

        for member in group_info["members"]:
            peer = await self.registry.get(member)
            if peer:
                asyncio.create_task(send_bg(
                    peer.writer,
                    {
                        "type": MSG_GROUP_MEMBER_REMOVED,
                        "group_id": group_id,
                        "group_name": group_info["group_name"],
                        "removed_member": member_to_remove,
                        "removed_by": removed_by,
                        "members": members_with_keys,
                    }
                ))

    async def _handle_store_offline(self, msg: dict) -> None:
        """Store an offline message on behalf of a peer."""
        await asyncio.to_thread(
            self.message_repo.store_offline_message,
            sender=msg["sender"],
            recipient=msg["recipient"],
            content_encrypted=msg["content_encrypted"],
            aes_key_encrypted=msg["aes_key_encrypted"],
            iv=msg["iv"],
            group_id=msg.get("group_id"),
            signature=msg.get("signature", ""),
            message_id=msg.get("message_id"),
        )

    # ── helpers ────────────────────────────────────────────

    async def _broadcast_peer_update(
        self, action: str, username: str, host: str, port: int, public_key: str
    ) -> None:
        """Notify all other peers about a join/leave event without blocking."""
        all_peers = await self.registry.get_all()
        msg = {
            "type": MSG_PEER_UPDATE,
            "action": action,
            "peer": {
                "username": username,
                "host": host,
                "port": port,
                "public_key": public_key,
            },
        }

        async def send_bg(writer, m):
            try:
                await Protocol.send_message(writer, m)
            except Exception:
                pass

        for peer in all_peers:
            if peer.username == username:
                continue
            asyncio.create_task(send_bg(peer.writer, msg))

    async def _peer_disconnected(self, username: str) -> None:
        """Clean up after a peer leaves."""
        peer = await self.registry.unregister(username)
        await self.heartbeat.remove(username)
        await asyncio.to_thread(self.user_repo.update_status, username, STATUS_OFFLINE)
        if peer:
            await self._broadcast_peer_update(
                ACTION_LEFT, username, peer.host, peer.port, peer.public_key
            )
        log.info("Peer disconnected: %s", username)

    async def _handle_dead_peer(self, username: str) -> None:
        """Called by the heartbeat monitor when a peer times out."""
        await self._peer_disconnected(username)

    async def _deliver_offline_messages(
        self, username: str, writer: asyncio.StreamWriter
    ) -> None:
        """Fetch and send pending offline messages."""
        messages = await asyncio.to_thread(self.message_repo.get_offline_messages, username)
        if not messages:
            return

        delivered_ids = []
        for m in messages:
            try:
                # Convert datetime for JSON
                ts = m.get("timestamp")
                if hasattr(ts, "isoformat"):
                    ts = ts.isoformat()

                msg_type = MSG_GROUP_MESSAGE if m.get("group_id") else MSG_CHAT_MESSAGE
                await Protocol.send_message(
                    writer,
                    {
                        "type": msg_type,
                        "message_id": m["message_id"],
                        "sender": m["sender"],
                        "recipient": m["recipient"],
                        "group_id": m.get("group_id"),
                        "content_encrypted": m["content_encrypted"],
                        "aes_key_encrypted": m["aes_key_encrypted"],
                        "iv": m["iv"],
                        "signature": m.get("signature", ""),
                        "timestamp": ts,
                        "offline": True,
                    },
                )
                delivered_ids.append(m["message_id"])
            except Exception as exc:
                log.error("Failed to deliver offline msg %s: %s", m["message_id"], exc)
                break

        if delivered_ids:
            count = await asyncio.to_thread(self.message_repo.mark_delivered, delivered_ids)
            log.info(
                "Marked %d offline messages delivered for %s", count, username
            )
