"""
Peer TCP server – listens for incoming connections from other peers.
"""

import asyncio

from network.protocol import Protocol
from utils.logger import get_logger

log = get_logger(__name__)


class PeerServer:
    """
    A TCP server that runs on the peer node and accepts connections
    from other peers for direct P2P messaging.
    """

    def __init__(self, host: str, port: int, peer_node) -> None:
        self.host = host
        self.port = port
        self.peer_node = peer_node  # back-reference to PeerNode
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        """Start listening for incoming peer connections."""
        self._server = await asyncio.start_server(
            self._handle_incoming, self.host, self.port
        )
        addr = self._server.sockets[0].getsockname()
        log.info("Peer server listening on %s:%d", addr[0], addr[1])

    async def _handle_incoming(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle one incoming peer connection."""
        peer_addr = writer.get_extra_info("peername")
        log.debug("Incoming peer connection from %s", peer_addr)

        try:
            while True:
                try:
                    msg = await Protocol.receive_message(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                if msg is None:
                    break

                await self.peer_node.message_handler.process(msg, writer)
        except Exception as exc:
            log.error("Error in incoming connection from %s: %s", peer_addr, exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.debug("Incoming connection closed: %s", peer_addr)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            log.info("Peer server stopped")
