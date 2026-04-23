class ReceiptError(Exception):
    """Base for receipt subsystem errors."""


class PrinterUnavailableError(ReceiptError):
    """USB printer not found or unreachable."""


class PrinterPaperOutError(ReceiptError):
    """Printer online but out of paper or cover open."""


class PrinterWriteError(ReceiptError):
    """Write to printer failed mid-stream."""
