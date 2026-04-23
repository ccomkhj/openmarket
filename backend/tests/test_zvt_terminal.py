import asyncio
from decimal import Decimal

import pytest

from app.payment.errors import (
    CardDeclinedError, TerminalTimeoutError, TerminalUnavailableError,
)
from app.payment.zvt import ZvtTerminal, frame_apdu


class _MockTcpTerminal:
    def __init__(self, *, decline: bool = False, timeout: bool = False, offline: bool = False):
        self.decline = decline
        self.timeout = timeout
        self.offline = offline
        self.requests: list[bytes] = []

    async def serve(self, host: str, port: int) -> asyncio.Server:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            data = await reader.read(1024)
            self.requests.append(data)
            if self.timeout:
                await asyncio.sleep(2.0)
                writer.close()
                return
            cls, ins = data[0], data[1]
            if cls == 0x05 and ins == 0x01:
                writer.write(frame_apdu(0x80, 0x00, b""))
            elif cls == 0x06 and ins == 0x01:
                code = b"\x84" if self.decline else b"\x00"
                payload = (
                    b"\x27" + code +
                    b"\x0B" + b"\x00\x00\x01" +
                    b"\x29" + b"\x12\x34\x56"
                )
                writer.write(frame_apdu(0x80, 0x00, payload))
            elif cls == 0x06 and ins == 0x30:
                writer.write(frame_apdu(0x80, 0x00, b"\x27\x00"))
            elif cls == 0x06 and ins == 0x50:
                writer.write(frame_apdu(0x80, 0x00, b"\x27\x00"))
            await writer.drain()
            writer.close()
        return await asyncio.start_server(handler, host, port)


@pytest.mark.asyncio
async def test_diagnose_online():
    mock = _MockTcpTerminal()
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000")
        assert await t.diagnose() is True
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_approved():
    mock = _MockTcpTerminal()
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000")
        result = await t.authorize(amount=Decimal("1.29"))
        assert result.approved is True
        assert result.response_code == "00"
        assert result.amount == Decimal("1.29")
        assert result.trace_number == "000001"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_declined_raises():
    mock = _MockTcpTerminal(decline=True)
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000", timeout_s=1)
        with pytest.raises(CardDeclinedError):
            await t.authorize(amount=Decimal("1.00"))
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_timeout_raises():
    mock = _MockTcpTerminal(timeout=True)
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000", timeout_s=0.5)
        with pytest.raises(TerminalTimeoutError):
            await t.authorize(amount=Decimal("1.00"))
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_unreachable_raises():
    t = ZvtTerminal(host="127.0.0.1", port=1, password="000000", timeout_s=0.5)
    with pytest.raises(TerminalUnavailableError):
        await t.diagnose()
