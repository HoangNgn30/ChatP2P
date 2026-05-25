"""
Peer registry – in-memory store of currently online peers.

Thread-safe via ``asyncio.Lock``.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class RegisteredPeer:
    """Runtime info for one connected peer."""

    username: str
    host: str
    port: int
    public_key: str
    writer: asyncio.StreamWriter
    reader: asyncio.StreamReader


class PeerRegistry:
    """In-memory registry of peers that are currently connected to the
    bootstrap server."""

    def __init__(self) -> None:
        self._peers: dict[str, RegisteredPeer] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        username: str,
        host: str,
        port: int,
        public_key: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        async with self._lock:
            old = self._peers.pop(username, None)
            if old:
                try:
                    old.writer.close()
                except Exception:
                    pass
            self._peers[username] = RegisteredPeer(
                username=username,
                host=host,
                port=port,
                public_key=public_key,
                writer=writer,
                reader=reader,
            )
        log.info("Peer registered: %s (%s:%d)", username, host, port)

    async def unregister(self, username: str) -> Optional[RegisteredPeer]:
        async with self._lock:
            peer = self._peers.pop(username, None)
        if peer:
            try:
                peer.writer.close()
            except Exception:
                pass
            log.info("Peer unregistered: %s", username)
        return peer

    async def get(self, username: str) -> Optional[RegisteredPeer]:
        async with self._lock:
            return self._peers.get(username)

    async def get_all(self) -> list[RegisteredPeer]:
        async with self._lock:
            return list(self._peers.values())

    async def get_peer_list_dicts(self, exclude: str = "") -> list[dict]:
        """Return serialisable peer list (for sending over the wire)."""
        async with self._lock:
            return [
                {
                    "username": p.username,
                    "host": p.host,
                    "port": p.port,
                    "public_key": p.public_key,
                }
                for p in self._peers.values()
                if p.username != exclude
            ]

    async def is_online(self, username: str) -> bool:
        async with self._lock:
            return username in self._peers

    async def count(self) -> int:
        async with self._lock:
            return len(self._peers)

    async def all_usernames(self) -> list[str]:
        async with self._lock:
            return list(self._peers.keys())
