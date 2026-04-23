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
