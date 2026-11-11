from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.database_url, pool_pre_ping=True, pool_recycle=1800,
    connect_args={"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
