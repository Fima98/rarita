from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, JSON
import uuid


class Category(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)

    products: List["Product"] = Relationship(back_populates="category")


class Product(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: str
    category_id: uuid.UUID = Field(foreign_key="category.id")
    attributes: dict = Field(default_factory=dict, sa_type=JSON)

    category: Optional[Category] = Relationship(back_populates="products")
    variants: List["ProductVariant"] = Relationship(back_populates="product")


class ProductVariant(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID = Field(foreign_key="product.id")
    sku: str = Field(unique=True, index=True)
    color_name: str
    color_hex: str
    price: float
    stock: int
    images: List[str] = Field(default_factory=list, sa_type=JSON)

    product: Optional[Product] = Relationship(back_populates="variants")
