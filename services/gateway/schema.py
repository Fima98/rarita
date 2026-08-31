from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any
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
