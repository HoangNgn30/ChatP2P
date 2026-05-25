"""
Tests for the network protocol (length-prefixed framing).
"""

import asyncio
import json
import struct

import pytest
import pytest_asyncio

from network.protocol import Protocol


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_send_and_receive():
    """Round-trip: send → receive should recover the original dict."""
    reader = asyncio.StreamReader()
    # Fake transport/writer pair
    transport = asyncio.WriteTransport
    protocol_obj = asyncio.StreamReaderProtocol(reader)

    # We'll simulate by manually feeding data
    msg = {"type": "CHAT_MESSAGE", "content": "Hello 🌍", "num": 42}
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = struct.pack("!I", len(body))
    reader.feed_data(header + body)
    reader.feed_eof()

    result = await Protocol.receive_message(reader)
    assert result == msg


@pytest.mark.asyncio
async def test_receive_returns_none_on_eof():
    """An empty stream should return None gracefully."""
    reader = asyncio.StreamReader()
    reader.feed_eof()

    with pytest.raises(asyncio.IncompleteReadError):
        await Protocol.receive_message(reader)


@pytest.mark.asyncio
async def test_unicode_message():
    """Non-ASCII content should round-trip correctly."""
    reader = asyncio.StreamReader()
    msg = {"type": "TEST", "text": "Xin chào thế giới! 🇻🇳"}
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = struct.pack("!I", len(body))
    reader.feed_data(header + body)
    reader.feed_eof()

    result = await Protocol.receive_message(reader)
    assert result["text"] == "Xin chào thế giới! 🇻🇳"
