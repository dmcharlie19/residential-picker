from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.config import settings
from app.models import ApartmentLot, ResidentialComplex
from app.sqlite import make_engine

@pytest.fixture(scope="session")
def database_engine(tmp_path_factory):
    # Always a unique temporary file, never the application file or an in-memory DB.
    path = tmp_path_factory.mktemp("database") / "catalog-test.sqlite3"
    url = "sqlite:///" + path.as_posix()
    previous = settings.database_url
    settings.database_url = url
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        engine = make_engine(url)
        yield engine
        engine.dispose()
    finally:
        settings.database_url = previous

@pytest.fixture
def db_session(database_engine):
    with Session(database_engine, expire_on_commit=False) as session:
        session.execute(delete(ApartmentLot))
        session.execute(delete(ResidentialComplex))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(ApartmentLot))
        session.execute(delete(ResidentialComplex))
        session.commit()
