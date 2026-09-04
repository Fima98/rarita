from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any, Optional
from uuid import UUID


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class CategoryCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class VariantCreateSchema(BaseModel):
    sku: str = Field(..., min_length=1,
                     description="Унікальний артикул товару")
    color_name: str
    color_hex: str = Field(..., pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
    price: float = Field(..., gt=0,
                         description="Ціна повинна бути більшою за 0")
    stock: int = Field(..., ge=0,
                       description="Кількість на складі (0 або більше)")
    images: List[str] = []


class ProductCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    category_id: UUID
    attributes: Dict[str, Any] = Field(default_factory=dict)
    variants: List[VariantCreateSchema] = Field(..., min_items=1)


class ProductUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProductVariantCreateSchema(BaseModel):
    sku: str
    color_name: str
    color_hex: str
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)
    images: list[str] = []


class ProductVariantUpdateSchema(BaseModel):
    price: Optional[float] = Field(default=None, gt=0)
    stock_delta: Optional[int] = Field(default=None)
    reserved_stock_delta: Optional[int] = Field(default=None)
    is_active: Optional[bool] = None


class OrderItemSchema(BaseModel):
    product_variant_id: str
    quantity: int


class CustomerInfoSchema(BaseModel):
    name: str
    phone: str
    email: EmailStr


class CreateOrderSchema(BaseModel):
    items: list[OrderItemSchema]
    customer: CustomerInfoSchema
    shipping_address: str


class ProcessPaymentSchema(BaseModel):
    order_id: str
    is_success: bool
