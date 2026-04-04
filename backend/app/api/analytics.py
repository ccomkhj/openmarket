from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, cast, Date, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.order import Order, LineItem
from app.schemas.analytics import AnalyticsSummary, DailySales, TopProduct

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def analytics_summary(days: int = 30, db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total revenue and order count
    totals_result = await db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_price), 0).label("total_revenue"),
        ).where(Order.created_at >= since)
    )
    totals = totals_result.one()
    total_orders = totals.total_orders
    total_revenue = Decimal(str(totals.total_revenue))
    average_order_value = (total_revenue / total_orders) if total_orders > 0 else Decimal("0")

    # Daily sales grouped by date
    daily_result = await db.execute(
        select(
            cast(Order.created_at, Date).label("date"),
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_price).label("revenue"),
        )
        .where(Order.created_at >= since)
        .group_by(cast(Order.created_at, Date))
        .order_by(cast(Order.created_at, Date))
    )
    daily_sales = [
        DailySales(
            date=str(row.date),
            order_count=row.order_count,
            revenue=Decimal(str(row.revenue)),
        )
        for row in daily_result.all()
    ]

    # Top products by quantity sold (limit 10)
    top_products_result = await db.execute(
        select(
            LineItem.title,
            func.sum(LineItem.quantity).label("quantity_sold"),
            func.sum(LineItem.quantity * LineItem.price).label("revenue"),
        )
        .join(Order, LineItem.order_id == Order.id)
        .where(Order.created_at >= since)
        .group_by(LineItem.title)
        .order_by(func.sum(LineItem.quantity).desc())
        .limit(10)
    )
    top_products = [
        TopProduct(
            title=row.title,
            quantity_sold=row.quantity_sold,
            revenue=Decimal(str(row.revenue)),
        )
        for row in top_products_result.all()
    ]

    # Orders by source
    source_result = await db.execute(
        select(
            Order.source,
            func.count(Order.id).label("count"),
        )
        .where(Order.created_at >= since)
        .group_by(Order.source)
    )
    orders_by_source = {row.source: row.count for row in source_result.all()}

    return AnalyticsSummary(
        total_revenue=total_revenue,
        total_orders=total_orders,
        average_order_value=average_order_value,
        daily_sales=daily_sales,
        top_products=top_products,
        orders_by_source=orders_by_source,
    )
