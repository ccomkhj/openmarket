"""USB printer transport and the ReceiptPrinter wrapper.

PrinterBackend abstracts the transport so tests inject DummyBackend and
production uses UsbBackend (python-escpos). The wire format (ESC/POS bytes)
is produced by ReceiptBuilder; this module only concerns itself with
pushing bytes and reading status.
"""
from __future__ import annotations

from typing import Protocol

from app.receipt.errors import (
    PrinterUnavailableError, PrinterPaperOutError, PrinterWriteError,
)


class PrinterBackend(Protocol):
    def write(self, data: bytes) -> None: ...
    def is_paper_ok(self) -> bool: ...
    def is_online(self) -> bool: ...


class DummyBackend:
    """In-memory printer for tests. Configurable fault injection."""

    def __init__(self, *, online: bool = True, paper_ok: bool = True):
        self.online = online
        self.paper_ok = paper_ok
        self.buffer: bytearray = bytearray()

    def write(self, data: bytes) -> None:
        if not self.online:
            raise PrinterUnavailableError("dummy offline")
        if not self.paper_ok:
            raise PrinterPaperOutError("dummy out of paper")
        self.buffer.extend(data)

    def is_paper_ok(self) -> bool:
        return self.paper_ok

    def is_online(self) -> bool:
        return self.online


class UsbBackend:
    """Real python-escpos USB transport. Not exercised in CI."""

    def __init__(self, vendor_id: int, product_id: int, profile: str):
        from escpos.printer import Usb
        try:
            self._p = Usb(vendor_id, product_id, profile=profile)
        except Exception as e:
            raise PrinterUnavailableError(f"USB open failed: {e}") from e

    def write(self, data: bytes) -> None:
        try:
            self._p._raw(data)
        except Exception as e:
            raise PrinterWriteError(str(e)) from e

    def is_paper_ok(self) -> bool:
        try:
            return bool(self._p.paper_status())
        except Exception:
            return False

    def is_online(self) -> bool:
        try:
            return self._p.is_online()
        except Exception:
            return False
