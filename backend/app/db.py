from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.sqlite import make_engine

engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as session:
        yield session
