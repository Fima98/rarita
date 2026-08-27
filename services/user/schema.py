from pydantic import BaseModel, EmailStr
import uuid


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
