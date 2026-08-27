from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from db import engine, get_session
from sqlmodel import SQLModel, Session, select
from models import User
from schema import UserCreate, UserRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "user"}


@app.post("/users/", response_model=UserRead)
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    db_user = User(**user.model_dump())
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.get("/users/", response_model=list[UserRead])
def read_user(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users
