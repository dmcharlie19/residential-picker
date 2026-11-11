"""Restore the preserved catalog to an empty, migrated SQLite file."""
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from sqlalchemy import Date, DateTime, select, func
from app.db import SessionLocal
from app.models import ResidentialComplex, ApartmentLot
from app.models.types import ScaledDecimal

payload=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
with SessionLocal() as session:
    with session.begin():
        if session.scalar(select(func.count()).select_from(ResidentialComplex)) or session.scalar(select(func.count()).select_from(ApartmentLot)):
            raise RuntimeError("Target SQLite file must be empty; existing data is never overwritten")
        for model in (ResidentialComplex, ApartmentLot):
            for source in payload[model.__tablename__]:
                row=dict(source)
                for column in model.__table__.columns:
                    value=row[column.name]
                    if value is None:
                        continue
                    if isinstance(column.type, ScaledDecimal): row[column.name]=Decimal(value)
                    elif isinstance(column.type, DateTime): row[column.name]=datetime.fromisoformat(value)
                    elif isinstance(column.type, Date): row[column.name]=date.fromisoformat(value)
                session.add(model(**row))
            session.flush()
    print({m.__tablename__:session.scalar(select(func.count()).select_from(m)) for m in (ResidentialComplex,ApartmentLot)})
