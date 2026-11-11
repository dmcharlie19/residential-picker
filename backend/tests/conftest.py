import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.models import ApartmentLot, ResidentialComplex


@pytest.fixture(scope="session")
def mysql_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run MySQL integration tests")
    if make_url(url).database != "residential_picker_test":
        raise RuntimeError("Tests may only modify residential_picker_test")
    if os.getenv("DATABASE_URL") != url:
        raise RuntimeError("Set DATABASE_URL and TEST_DATABASE_URL to the same dedicated test database")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(mysql_engine):
    with Session(mysql_engine, expire_on_commit=False) as session:
        session.execute(delete(ApartmentLot))
        session.execute(delete(ResidentialComplex))
        session.commit()
        yield session
        session.rollback()
        session.execute(delete(ApartmentLot))
        session.execute(delete(ResidentialComplex))
        session.commit()
