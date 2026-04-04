from decimal import Decimal
from pydantic import BaseModel


class DailySales(BaseModel):
    date: str
    order_count: int
    revenue: Decimal


class TopProduct(BaseModel):
    title: str
    quantity_sold: int
    revenue: Decimal


class AnalyticsSummary(BaseModel):
    total_revenue: Decimal
    total_orders: int
    average_order_value: Decimal
    daily_sales: list[DailySales]
    top_products: list[TopProduct]
    orders_by_source: dict[str, int]
