"""Minimal DSFinV-K export — bundles audit-critical CSVs into a ZIP."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    KassenbuchEntry, PosTransaction, PosTransactionLine,
)


class DsfinvkExporter:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def export(self, *, date_from: datetime, date_to: datetime) -> bytes:
        txs = (await self.db.execute(
            select(PosTransaction).where(
                and_(PosTransaction.started_at >= date_from,
                     PosTransaction.started_at <= date_to)
            ).order_by(PosTransaction.receipt_number)
        )).scalars().all()
        lines = (await self.db.execute(
            select(PosTransactionLine).where(
                PosTransactionLine.pos_transaction_id.in_([t.id for t in txs]) if txs else False
            )
        )).scalars().all() if txs else []
        kb = (await self.db.execute(
            select(KassenbuchEntry).where(
                and_(KassenbuchEntry.timestamp >= date_from,
                     KassenbuchEntry.timestamp <= date_to)
            )
        )).scalars().all()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bonkopf.csv", _bonkopf(txs))
            zf.writestr("bonpos.csv", _bonpos(txs, lines))
            zf.writestr("bonkopf_zahlarten.csv", _zahlarten(txs))
            zf.writestr("tse.csv", _tse(txs))
            zf.writestr("cash_per_currency.csv", _cash_per_currency(kb))
            zf.writestr("index.xml", _index_xml(date_from, date_to))
        return buf.getvalue()


def _csv(headers, rows) -> str:
    out = io.StringIO()
    out.write("﻿")  # BOM for UTF-8 detection
    w = csv.DictWriter(out, fieldnames=headers, delimiter=";")
    w.writeheader()
    for r in rows:
        w.writerow({h: r.get(h, "") for h in headers})
    return out.getvalue()


def _bonkopf(txs):
    headers = ["Z_KASSE_ID","Z_ERSTELLUNG","Z_NR","BON_ID","BON_NR","BON_TYP","BON_NAME",
               "TERMINAL_ID","BON_STORNO","BON_START","BON_ENDE","BEDIENER_NAME","UMS_BRUTTO"]
    rows = []
    for t in txs:
        rows.append({
            "Z_KASSE_ID": settings.merchant_register_id,
            "Z_ERSTELLUNG": (t.finished_at or t.started_at).isoformat(),
            "Z_NR": t.receipt_number,
            "BON_ID": str(t.id),
            "BON_NR": t.receipt_number,
            "BON_TYP": "Beleg" if t.voids_transaction_id is None else "AVBeleg",
            "BON_NAME": "Kassenbeleg-V1",
            "TERMINAL_ID": settings.merchant_register_id,
            "BON_STORNO": "1" if t.voids_transaction_id is not None else "0",
            "BON_START": t.started_at.isoformat(),
            "BON_ENDE": (t.finished_at or t.started_at).isoformat(),
            "BEDIENER_NAME": str(t.cashier_user_id),
            "UMS_BRUTTO": _d(t.total_gross),
        })
    return _csv(headers, rows)


def _bonpos(txs, lines):
    by_tx = {t.id: t for t in txs}
    headers = ["Z_KASSE_ID","Z_ERSTELLUNG","BON_ID","POS_ZEILE","GUTSCHEIN_NR","ARTIKELTEXT",
               "MENGE","FAKTOR","UMS_BRUTTO","UST_SCHLUESSEL","STNR"]
    rows = []
    for i, ln in enumerate(lines):
        t = by_tx.get(ln.pos_transaction_id)
        if not t:
            continue
        rows.append({
            "Z_KASSE_ID": settings.merchant_register_id,
            "Z_ERSTELLUNG": (t.finished_at or t.started_at).isoformat(),
            "BON_ID": str(t.id),
            "POS_ZEILE": i + 1,
            "ARTIKELTEXT": ln.title,
            "MENGE": _d(ln.quantity),
            "FAKTOR": "1",
            "UMS_BRUTTO": _d(ln.line_total_net + ln.vat_amount),
            "UST_SCHLUESSEL": _ust_schluessel(ln.vat_rate),
            "STNR": ln.sku or "",
        })
    return _csv(headers, rows)


def _zahlarten(txs):
    headers = ["Z_KASSE_ID","BON_ID","ZAHLART_TYP","ZAHLART_NAME","BETRAG"]
    rows = []
    for t in txs:
        for method, amount in (t.payment_breakdown or {}).items():
            rows.append({
                "Z_KASSE_ID": settings.merchant_register_id,
                "BON_ID": str(t.id),
                "ZAHLART_TYP": "Bar" if method == "cash" else "Unbar",
                "ZAHLART_NAME": method,
                "BETRAG": _d(amount),
            })
    return _csv(headers, rows)


def _tse(txs):
    headers = ["Z_KASSE_ID","BON_ID","TSE_ID","TSE_TA_NR","TSE_TA_START","TSE_TA_ENDE",
               "TSE_TA_VORGANGSART","TSE_TA_SIGZ","TSE_TA_SIG","TSE_TA_FEHLER"]
    rows = []
    for t in txs:
        rows.append({
            "Z_KASSE_ID": settings.merchant_register_id,
            "BON_ID": str(t.id),
            "TSE_ID": t.tse_serial or "",
            "TSE_TA_NR": "",
            "TSE_TA_START": t.tse_timestamp_start.isoformat() if t.tse_timestamp_start else "",
            "TSE_TA_ENDE": t.tse_timestamp_finish.isoformat() if t.tse_timestamp_finish else "",
            "TSE_TA_VORGANGSART": t.tse_process_type or "",
            "TSE_TA_SIGZ": t.tse_signature_counter or "",
            "TSE_TA_SIG": t.tse_signature or "",
            "TSE_TA_FEHLER": "1" if t.tse_pending else "0",
        })
    return _csv(headers, rows)


def _cash_per_currency(kb):
    headers = ["Z_KASSE_ID","WAEHRUNG","Z_SAFR_AME","Z_SAFR_NEN"]
    cash_total = sum(
        (Decimal(e.amount) for e in kb if e.entry_type in ("open","close","paid_in","paid_out")),
        Decimal("0"),
    )
    return _csv(headers, [{
        "Z_KASSE_ID": settings.merchant_register_id,
        "WAEHRUNG": "EUR",
        "Z_SAFR_AME": _d(cash_total),
        "Z_SAFR_NEN": _d(cash_total),
    }])


def _index_xml(date_from, date_to) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<DataSet>
  <Description>OpenMarket DSFinV-K minimal export {date_from.date()} - {date_to.date()}</Description>
  <Tables>
    <Table><URL>bonkopf.csv</URL></Table>
    <Table><URL>bonpos.csv</URL></Table>
    <Table><URL>bonkopf_zahlarten.csv</URL></Table>
    <Table><URL>tse.csv</URL></Table>
    <Table><URL>cash_per_currency.csv</URL></Table>
  </Tables>
</DataSet>
"""


def _d(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.01'))}"


def _ust_schluessel(rate) -> str:
    return {Decimal("19"): "1", Decimal("7"): "2", Decimal("10.7"): "3",
            Decimal("5.5"): "4", Decimal("0"): "5"}.get(
        Decimal(rate).quantize(Decimal("0.1")).normalize(), "5")
