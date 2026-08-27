from sqlmodel import create_engine, Session
from pathlib import Path


DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "database.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)


def get_session():
    with Session(engine) as session:
        yield session
