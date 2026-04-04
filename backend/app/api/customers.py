from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.customer import Customer, CustomerAddress
from app.models.order import Order
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.schemas.order import OrderListOut

router = APIRouter(prefix="/api", tags=["customers"])


@router.post("/customers", response_model=CustomerOut, status_code=201)
async def create_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
    )
    for addr in body.addresses:
        customer.addresses.append(CustomerAddress(**addr.model_dump()))
    db.add(customer)
    await db.commit()
    await db.refresh(customer, ["addresses"])
    return customer


@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Customer).options(selectinload(Customer.addresses)).order_by(Customer.id)
    )
    return result.scalars().all()


@router.get("/customers/lookup", response_model=CustomerOut)
async def lookup_customer(
    email: str | None = None,
    phone: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Provide email or phone")
    query = select(Customer).options(selectinload(Customer.addresses))
    if phone:
        query = query.where(Customer.phone == phone)
    elif email:
        query = query.where(Customer.email == email)
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.addresses))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: int, body: CustomerUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.addresses))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    await db.commit()
    await db.refresh(customer, ["addresses"])
    return customer


@router.get("/customers/{customer_id}/orders", response_model=list[OrderListOut])
async def get_customer_orders(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()
