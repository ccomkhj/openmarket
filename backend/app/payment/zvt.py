"""Minimal ZVT-700 framing + amount BCD encoding.

Reference: ZVT 700 Spezifikation v1.13. We implement only what the four
day-1 commands need (Authorisation 06 01, Reversal 06 30, EOD 06 50,
Diagnosis 05 01).
"""
from __future__ import annotations

from decimal import Decimal


def frame_apdu(cls: int, ins: int, data: bytes) -> bytes:
    """Build a ZVT APDU.
    Length is 1 byte if <0xFF, otherwise 0xFF + 2-byte little-endian length.
    """
    n = len(data)
    if n < 0xFF:
        return bytes([cls, ins, n]) + data
    return bytes([cls, ins, 0xFF]) + n.to_bytes(2, "little") + data


def parse_apdu(buf: bytes) -> tuple[int, int, bytes]:
    cls, ins = buf[0], buf[1]
    if buf[2] == 0xFF:
        n = int.from_bytes(buf[3:5], "little")
        payload = buf[5:5 + n]
    else:
        n = buf[2]
        payload = buf[3:3 + n]
    if len(payload) != n:
        raise ValueError(f"truncated APDU: declared {n}, got {len(payload)}")
    return cls, ins, payload


def encode_amount_bcd(amount: Decimal) -> bytes:
    """Encode a Euro amount as 6 BCD digits, one digit per byte (unpacked).

    NOTE: ZVT amount encoding has two conventions — 6 BCD digits packed (3 bytes)
    and unpacked (6 bytes). We use unpacked here; if your terminal expects packed,
    change encoder + tests accordingly.
    """
    cents = int((amount * 100).quantize(Decimal("1")))
    if cents < 0 or cents > 999_999:
        raise ValueError(f"amount {amount} outside 0–9999.99 EUR")
    s = f"{cents:06d}"
    return bytes(int(c) for c in s)


def decode_amount_bcd(data: bytes) -> Decimal:
    if len(data) != 6:
        raise ValueError(f"expected 6 BCD digits, got {len(data)}")
    cents = int("".join(str(b) for b in data))
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


import asyncio

from app.payment.errors import (
    CardDeclinedError, TerminalProtocolError, TerminalTimeoutError,
    TerminalUnavailableError,
)
from app.payment.terminal import AuthorizeResult


def _parse_bmp(payload: bytes) -> dict[int, bytes]:
    """Parse ZVT BMP TLV for fixed-length tags we use."""
    fixed = {0x27: 1, 0x0B: 3, 0x29: 3}
    out: dict[int, bytes] = {}
    i = 0
    while i < len(payload):
        tag = payload[i]; i += 1
        n = fixed.get(tag, 0)
        if n == 0:
            break
        out[tag] = payload[i:i + n]; i += n
    return out


class ZvtTerminal:
    def __init__(
        self, *, host: str, port: int, password: str = "000000",
        timeout_s: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.timeout_s = timeout_s

    async def _exchange(self, cls: int, ins: int, data: bytes) -> bytes:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_s,
            )
        except (OSError, asyncio.TimeoutError) as e:
            raise TerminalUnavailableError(f"{self.host}:{self.port}: {e}") from e
        try:
            writer.write(frame_apdu(cls, ins, data))
            await writer.drain()
            try:
                resp = await asyncio.wait_for(reader.read(8192), timeout=self.timeout_s)
            except asyncio.TimeoutError as e:
                raise TerminalTimeoutError(f"no response in {self.timeout_s}s") from e
            if not resp:
                raise TerminalProtocolError("empty response")
            r_cls, r_ins, payload = parse_apdu(resp)
            if (r_cls, r_ins) != (0x80, 0x00):
                raise TerminalProtocolError(f"unexpected response APDU {r_cls:02X} {r_ins:02X}")
            return payload
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def diagnose(self) -> bool:
        await self._exchange(0x05, 0x01, b"")
        return True

    async def authorize(self, *, amount: Decimal) -> AuthorizeResult:
        body = bytes([0x49, 0x78]) + encode_amount_bcd(amount)  # currency 0x4978 = EUR
        payload = await self._exchange(0x06, 0x01, body)
        bmps = _parse_bmp(payload)
        if 0x27 not in bmps:
            raise TerminalProtocolError("missing response-code BMP 0x27")
        code = bmps[0x27].hex()
        trace = bmps.get(0x0B, b"\x00\x00\x00").hex().zfill(6)
        auth = bmps.get(0x29, b"\x00\x00\x00").hex().zfill(6)
        if code != "00":
            raise CardDeclinedError(f"response code {code}")
        return AuthorizeResult(
            approved=True, amount=amount,
            auth_code=auth, terminal_id=f"{self.host}:{self.port}",
            trace_number=trace, receipt_number=trace,
            response_code=code, raw={"bmp": {hex(k): v.hex() for k, v in bmps.items()}},
        )

    async def reverse(self, *, trace_number: str) -> AuthorizeResult:
        trace_b = bytes.fromhex(trace_number.zfill(6))
        body = b"\x0B" + trace_b
        payload = await self._exchange(0x06, 0x30, body)
        bmps = _parse_bmp(payload)
        return AuthorizeResult(
            approved=bmps.get(0x27, b"\xff").hex() == "00",
            amount=Decimal("0"), auth_code="000000",
            terminal_id=f"{self.host}:{self.port}",
            trace_number=trace_number, receipt_number=trace_number,
            response_code=bmps.get(0x27, b"\xff").hex(), raw={},
        )

    async def end_of_day(self) -> dict:
        payload = await self._exchange(0x06, 0x50, b"")
        bmps = _parse_bmp(payload)
        return {"completed": bmps.get(0x27, b"\xff").hex() == "00"}
