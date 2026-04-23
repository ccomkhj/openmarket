from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_manager_or_above, require_owner
from app.reports.dsfinvk import DsfinvkExporter
from app.reports.z_report import ZReportBuilder


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/z-report", dependencies=[Depends(require_manager_or_above)])
async def z_report(
    date_from: datetime, date_to: datetime,
    db: AsyncSession = Depends(get_db),
):
    rpt = await ZReportBuilder(db=db).build(date_from=date_from, date_to=date_to)
    return {
        "date_from": rpt.date_from.isoformat(),
        "date_to": rpt.date_to.isoformat(),
        "opening_cash": str(rpt.opening_cash),
        "closing_counted": str(rpt.closing_counted),
        "transaction_count": rpt.transaction_count,
        "sales_by_vat": {k: str(v) for k, v in rpt.sales_by_vat.items()},
        "sales_by_payment": {k: str(v) for k, v in rpt.sales_by_payment.items()},
        "paid_in_total": str(rpt.paid_in_total),
        "paid_out_total": str(rpt.paid_out_total),
        "signature_counter_first": rpt.signature_counter_first,
        "signature_counter_last": rpt.signature_counter_last,
    }


@router.get("/dsfinvk", dependencies=[Depends(require_owner)])
async def dsfinvk_export(
    date_from: date, date_to: date,
    db: AsyncSession = Depends(get_db),
):
    df = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    dt = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
    raw = await DsfinvkExporter(db=db).export(date_from=df, date_to=dt)
    return Response(
        content=raw, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dsfinvk-{date_from}-{date_to}.zip"'},
    )
