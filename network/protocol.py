"""
Network protocol – length-prefixed framing over TCP.

Every message is sent as:
    [4-byte big-endian length] [JSON-encoded UTF-8 body]

This guarantees we always read exactly one complete message at a time,
regardless of TCP segment boundaries.
"""

import asyncio
import json
import struct
from typing import Optional

from utils.constants import HEADER_SIZE, MAX_MESSAGE_SIZE
from utils.logger import get_logger

log = get_logger(__name__)


class Protocol:
    """Send and receive length-prefixed JSON messages over asyncio streams."""

    @staticmethod
    async def send_message(writer: asyncio.StreamWriter, message: dict) -> None:
        """
        Serialise *message* to JSON, prepend a 4-byte length header, and
        write to *writer*.

        Raises ``ConnectionError`` if the transport is already closed.
        """
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        length = len(body)

        if length > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message too large: {length} bytes (max {MAX_MESSAGE_SIZE})"
            )

        header = struct.pack("!I", length)  # big-endian unsigned 32-bit int
        writer.write(header + body)
        await writer.drain()
        log.debug("Sent %d bytes  type=%s", length, message.get("type", "?"))

    @staticmethod
    async def receive_message(
        reader: asyncio.StreamReader,
    ) -> Optional[dict]:
        """
        Read one complete message from *reader*.

        Returns the parsed dict, or ``None`` if the connection was closed
        before a full message could be read.
        """
        # 1. Read header
        header_data = await reader.readexactly(HEADER_SIZE)
        if not header_data:
            return None

        (length,) = struct.unpack("!I", header_data)

        if length > MAX_MESSAGE_SIZE:
            log.warning("Incoming message claims %d bytes – dropping", length)
            return None

        # 2. Read body
        body_data = await reader.readexactly(length)
        message = json.loads(body_data.decode("utf-8"))
        log.debug("Received %d bytes  type=%s", length, message.get("type", "?"))
        return message
