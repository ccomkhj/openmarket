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


def get_backend() -> "PrinterBackend":
    """Module-level factory: return a cached backend instance.

    Constructed once at first call so the USB connection is not re-opened on
    every HTTP request. Plan C (payment.py) and beyond can import this instead
    of re-implementing the fallback logic.
    """
    return _backend_cache()


def _build_backend() -> "PrinterBackend":
    from app.config import settings
    if not settings.printer_vendor_id:
        return DummyBackend()
    try:
        return UsbBackend(
            vendor_id=settings.printer_vendor_id,
            product_id=settings.printer_product_id,
            profile=settings.printer_profile,
        )
    except PrinterUnavailableError:
        return DummyBackend(online=False)


# Lazy singleton — built on first access, reused for the process lifetime.
_cached_backend: "PrinterBackend | None" = None


def _backend_cache() -> "PrinterBackend":
    global _cached_backend
    if _cached_backend is None:
        _cached_backend = _build_backend()
    return _cached_backend


class PrinterBackend(Protocol):
    def write(self, data: bytes) -> None: ...
    def is_paper_ok(self) -> bool: ...
    def is_online(self) -> bool: ...
    def pulse_cash_drawer(self) -> None: ...


class DummyBackend:
    """In-memory printer for tests. Configurable fault injection."""

    def __init__(self, *, online: bool = True, paper_ok: bool = True):
        self.online = online
        self.paper_ok = paper_ok
        self.buffer: bytearray = bytearray()
        self.drawer_pulses: int = 0

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

    def pulse_cash_drawer(self) -> None:
        if not self.online:
            raise PrinterUnavailableError("dummy offline")
        self.drawer_pulses += 1


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

    def pulse_cash_drawer(self) -> None:
        try:
            # ESC p m t1 t2 — open drawer pin 2 (m=0), 50ms pulse.
            self._p._raw(b"\x1b\x70\x00\x32\x32")
        except Exception as e:
            raise PrinterWriteError(str(e)) from e
