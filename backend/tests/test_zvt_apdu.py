from decimal import Decimal
from app.payment.zvt import (
    frame_apdu, parse_apdu, encode_amount_bcd, decode_amount_bcd,
)


def test_frame_short_length():
    out = frame_apdu(0x06, 0x01, b"\xAA\xBB")
    assert out == bytes([0x06, 0x01, 0x02, 0xAA, 0xBB])


def test_frame_long_length():
    payload = b"\x00" * 300
    out = frame_apdu(0x06, 0x01, payload)
    assert out[:3] == bytes([0x06, 0x01, 0xFF])
    assert out[3:5] == (300).to_bytes(2, "little")
    assert out[5:] == payload
    assert len(out) == 5 + 300


def test_parse_short_length():
    raw = bytes([0x80, 0x00, 0x03, 0x11, 0x22, 0x33])
    cls, ins, payload = parse_apdu(raw)
    assert (cls, ins) == (0x80, 0x00)
    assert payload == b"\x11\x22\x33"


def test_parse_long_length():
    raw = bytes([0x80, 0x00, 0xFF]) + (4).to_bytes(2, "little") + b"\xAA\xBB\xCC\xDD"
    cls, ins, payload = parse_apdu(raw)
    assert payload == b"\xAA\xBB\xCC\xDD"


def test_encode_amount_bcd_6_digits():
    # 1.29 EUR unpacked BCD 6 digits: 000129 → bytes(0,0,0,1,2,9)
    assert encode_amount_bcd(Decimal("1.29")) == bytes([0, 0, 0, 1, 2, 9])


def test_decode_amount_roundtrip():
    for amt in (Decimal("0.01"), Decimal("1.29"), Decimal("999.99")):
        assert decode_amount_bcd(encode_amount_bcd(amt)) == amt
