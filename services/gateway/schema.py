from pydantic import BaseModel, EmailStr
import uuid


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
