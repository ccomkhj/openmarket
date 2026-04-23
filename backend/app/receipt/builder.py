"""Pure ESC/POS byte-stream builder for an 80mm thermal receipt.

The output is deterministic: given the same inputs, byte-identical output.
This is enforced by the golden test in tests/test_receipt_builder.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from escpos.printer import Dummy

from app.models import PosTransaction, PosTransactionLine


_VAT_LETTER_BY_RATE = {
    Decimal("7"): "A",
    Decimal("19"): "B",
    Decimal("10.7"): "C",
    Decimal("0"): "D",
    Decimal("5.5"): "E",
}


@dataclass
class ReceiptBuilder:
    merchant_name: str
    merchant_address: str
    merchant_tax_id: str
    merchant_vat_id: str
    cashier_display: str
    register_id: str

    def render(self, tx: PosTransaction, lines: Sequence[PosTransactionLine]) -> bytes:
        p = Dummy()
        self._header(p)
        p.set(align="center", bold=True)
        p.textln(self.merchant_name)
        p.set(align="center", bold=False)
        p.textln(self.merchant_address)
        p.textln(f"St-Nr: {self.merchant_tax_id}")
        p.textln(f"USt-IdNr: {self.merchant_vat_id}")
        self._sep(p)
        p.set(align="left")
        p.textln(f"Datum:  {_fmt_dt(tx.finished_at or tx.started_at)}")
        p.textln(f"Beleg-Nr: {_fmt_receipt_number(tx.receipt_number, tx.started_at.year)}")
        p.textln(f"Kasse:  {self.register_id}")
        p.textln(f"Bediener: {self.cashier_display}")
        self._sep(p)

        for ln in lines:
            letter = _VAT_LETTER_BY_RATE.get(
                Decimal(ln.vat_rate).quantize(Decimal("0.1")).normalize(), "?"
            )
            p.textln(ln.title)
            if ln.quantity_kg is not None:
                p.textln(
                    f"  {_fmt_qty(ln.quantity_kg)} kg x {_fmt_money(ln.unit_price)} EUR/kg"
                    f"  {_fmt_money(ln.line_total_net + ln.vat_amount)} {letter}"
                )
            else:
                p.textln(
                    f"  {int(ln.quantity)} x {_fmt_money(ln.unit_price)}"
                    f"  {_fmt_money(ln.line_total_net + ln.vat_amount)} {letter}"
                )
        self._sep(p)

        p.set(bold=True)
        p.textln(f"GESAMTSUMME          {_fmt_money(tx.total_gross)} EUR")
        p.set(bold=False)
        p.textln("")
        p.textln("  Netto   USt   Brutto")
        for rate, amounts in tx.vat_breakdown.items():
            letter = _VAT_LETTER_BY_RATE.get(Decimal(rate), "?")
            p.textln(
                f"{letter} {rate}%  {_fmt_money(amounts['vat'])}"
                f"   {_fmt_money(amounts['gross'])}  {_fmt_money(amounts['net'])}"
            )
        p.textln("")
        p.textln("Bezahlt mit:")
        for method, amount in tx.payment_breakdown.items():
            label = {"cash": "Bar", "girocard": "Girocard", "card": "Karte"}.get(method, method)
            p.textln(f"  {label:<20}{_fmt_money(amount)} EUR")
        self._sep(p)
        p.textln("TSE-Signatur")
        p.textln(f"Seriennr: {_truncate(tx.tse_serial or '', 30)}")
        p.textln(f"Sig-Zaehler: {tx.tse_signature_counter or ''}")
        p.textln(f"Start: {_fmt_iso(tx.tse_timestamp_start)}")
        p.textln(f"Ende:  {_fmt_iso(tx.tse_timestamp_finish)}")
        p.textln(f"Typ:   {tx.tse_process_type or ''}")
        p.textln(f"Sig:   {_truncate(tx.tse_signature or '', 40)}")
        self._sep(p)
        p.set(align="center")
        p.textln("Vielen Dank fuer Ihren Einkauf!")
        p.textln("")
        p.cut()
        return p.output

    def _sep(self, p: Dummy) -> None:
        p.set(align="left")
        p.textln("-" * 32)

    def _header(self, p: Dummy) -> None:
        p.hw("INIT")


def _fmt_money(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.01')):>6.2f}"


def _fmt_qty(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.001'))}"


def _fmt_dt(d) -> str:
    return d.strftime("%d.%m.%Y  %H:%M") if d else ""


def _fmt_iso(d) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z" if d else ""


def _fmt_receipt_number(n: int, year: int) -> str:
    return f"{year}-{n:06d}"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."
