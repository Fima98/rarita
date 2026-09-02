import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True, nullable=True)
    status: str = Field(default="PENDING")  # PENDING, PAID, CANCELLED
    total_price: float

    customer_name: str
    customer_phone: str
    customer_email: str
    shipping_address: str

    created_at: datetime = Field(default_factory=datetime.utcnow)

    items: List["OrderItem"] = Relationship(back_populates="order")


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id")
    product_variant_id: str
    quantity: int
    price: float

    order: Optional[Order] = Relationship(back_populates="items")
