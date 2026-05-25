"""
Peer TCP client – manages outgoing connections to other peers.
"""

import asyncio

from network.connection import ConnectionManager, PeerInfo
from network.protocol import Protocol
from utils.logger import get_logger

log = get_logger(__name__)


class PeerClient:
    """
    Manages outgoing TCP connections from this peer to other peers.
    """

    def __init__(self, peer_node) -> None:
        self.peer_node = peer_node
        self.connections = ConnectionManager()

    async def connect(self, peer_info: PeerInfo) -> bool:
        """
        Establish a TCP connection to another peer.
        Returns True on success.
        """
        if await self.connections.is_connected(peer_info.username):
            return True

        try:
            reader, writer = await asyncio.open_connection(
                peer_info.host, peer_info.port
            )
            await self.connections.add(
                peer_info.username, reader, writer, peer_info
            )

            # Start background reader for this connection
            asyncio.ensure_future(
                self._read_loop(peer_info.username, reader)
            )

            log.info(
                "Connected to peer: %s (%s:%d)",
                peer_info.username,
                peer_info.host,
                peer_info.port,
            )
            return True
        except (ConnectionRefusedError, OSError) as exc:
            log.warning(
                "Cannot connect to %s (%s:%d): %s",
                peer_info.username,
                peer_info.host,
                peer_info.port,
                exc,
            )
            return False

    async def send(self, username: str, message: dict) -> bool:
        """Send a message to a connected peer.  Returns True on success."""
        writer = await self.connections.get_writer(username)
        if writer is None:
            log.warning("No connection to %s – cannot send", username)
            return False
        try:
            await Protocol.send_message(writer, message)
            return True
        except (ConnectionError, OSError) as exc:
            log.warning("Send to %s failed: %s", username, exc)
            await self.connections.remove(username)
            return False

    async def disconnect(self, username: str) -> None:
        await self.connections.remove(username)

    async def disconnect_all(self) -> None:
        await self.connections.close_all()

    async def is_connected(self, username: str) -> bool:
        return await self.connections.is_connected(username)

    # ── internal ───────────────────────────────────────────

    async def _read_loop(
        self, username: str, reader: asyncio.StreamReader
    ) -> None:
        """Background task: read messages from a peer connection."""
        try:
            while True:
                try:
                    msg = await Protocol.receive_message(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                if msg is None:
                    break
                await self.peer_node.message_handler.process(msg, None)
        except Exception as exc:
            log.error("Read loop error for %s: %s", username, exc)
        finally:
            await self.connections.remove(username)
            log.debug("Read loop ended for %s", username)
