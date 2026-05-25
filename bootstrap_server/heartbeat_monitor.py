"""
Heartbeat monitor – detects dead peers and triggers cleanup.

Runs as a background asyncio task inside the bootstrap server.
"""

import asyncio
import time

from bootstrap_server.peer_registry import PeerRegistry
from utils.constants import DEFAULT_HEARTBEAT_TIMEOUT
from utils.logger import get_logger

log = get_logger(__name__)


class HeartbeatMonitor:
    """
    Tracks the last heartbeat timestamp for each peer.

    A background coroutine checks every ``check_interval`` seconds whether
    any peer has exceeded ``timeout``.  When it has, the ``on_dead_peer``
    callback is invoked so the server can clean up.
    """

    def __init__(
        self,
        registry: PeerRegistry,
        timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
        check_interval: int = 10,
    ) -> None:
        self.registry = registry
        self.timeout = timeout
        self.check_interval = check_interval
        self._last_heartbeat: dict[str, float] = {}  # username → monotonic ts
        self._lock = asyncio.Lock()
        self._running = False
        self._task: asyncio.Task | None = None
        self.on_dead_peer = None  # async callback(username)

    # ── public API ─────────────────────────────────────────

    async def update(self, username: str) -> None:
        """Record that *username* is alive right now."""
        async with self._lock:
            self._last_heartbeat[username] = time.monotonic()

    async def remove(self, username: str) -> None:
        """Stop tracking *username*."""
        async with self._lock:
            self._last_heartbeat.pop(username, None)

    def start(self) -> None:
        """Spawn the background checker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._check_loop())
        log.info(
            "Heartbeat monitor started  timeout=%ds  interval=%ds",
            self.timeout,
            self.check_interval,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── internal ───────────────────────────────────────────

    async def _check_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.check_interval)
            await self._sweep()

    async def _sweep(self) -> None:
        now = time.monotonic()
        dead: list[str] = []

        async with self._lock:
            for username, ts in list(self._last_heartbeat.items()):
                if now - ts > self.timeout:
                    dead.append(username)
            for u in dead:
                self._last_heartbeat.pop(u, None)

        for username in dead:
            log.warning("Peer timed out (no heartbeat): %s", username)
            if self.on_dead_peer:
                await self.on_dead_peer(username)
