from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker  # declarative_base moved in SQLAlchemy 2.0
from app.config import settings

DATABASE_URL = settings.DATABASE_URL

# Normalise postgres:// → postgresql:// (required by SQLAlchemy 1.4+)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite requires check_same_thread=False for multi-threaded use (e.g. TestClient)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
