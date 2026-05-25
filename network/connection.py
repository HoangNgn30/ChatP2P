"""
Connection manager – tracks active TCP connections with auto-cleanup.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class PeerInfo:
    """Information about a known peer."""

    username: str
    host: str
    port: int
    public_key: str = ""


@dataclass
class ConnectionEntry:
    """A live TCP connection to a peer."""

    peer_info: PeerInfo
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter


class ConnectionManager:
    """Thread-safe pool of TCP connections keyed by username."""

    def __init__(self) -> None:
        self._connections: dict[str, ConnectionEntry] = {}
        self._lock = asyncio.Lock()

    # ── public API ─────────────────────────────────────────

    async def add(
        self,
        username: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        peer_info: Optional[PeerInfo] = None,
    ) -> None:
        """Register a connection.  Closes any previous one for the same user."""
        async with self._lock:
            old = self._connections.pop(username, None)
            if old:
                old.writer.close()
                log.debug("Replaced old connection for %s", username)

            if peer_info is None:
                peer_info = PeerInfo(username=username, host="", port=0)

            self._connections[username] = ConnectionEntry(
                peer_info=peer_info, reader=reader, writer=writer
            )
            log.debug("Connection added: %s", username)

    async def remove(self, username: str) -> None:
        """Close and remove a connection."""
        async with self._lock:
            entry = self._connections.pop(username, None)
        if entry:
            try:
                entry.writer.close()
                await entry.writer.wait_closed()
            except Exception:
                pass
            log.debug("Connection removed: %s", username)

    async def get(self, username: str) -> Optional[ConnectionEntry]:
        """Return the connection entry or ``None``."""
        async with self._lock:
            return self._connections.get(username)

    async def get_writer(self, username: str) -> Optional[asyncio.StreamWriter]:
        """Shorthand – return just the writer."""
        entry = await self.get(username)
        return entry.writer if entry else None

    async def is_connected(self, username: str) -> bool:
        entry = await self.get(username)
        if entry is None:
            return False
        return not entry.writer.is_closing()

    async def all_usernames(self) -> list[str]:
        async with self._lock:
            return list(self._connections.keys())

    async def close_all(self) -> None:
        """Close every connection."""
        async with self._lock:
            for username, entry in self._connections.items():
                try:
                    entry.writer.close()
                except Exception:
                    pass
            self._connections.clear()
        log.info("All connections closed")
