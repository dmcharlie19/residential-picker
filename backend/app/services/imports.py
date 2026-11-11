from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ApartmentLot, ResidentialComplex
from app.schemas.imports import ComplexSnapshot, LotSnapshot


class ImportFailure(ValueError):
    """A complete import was rejected; no changes were committed."""


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0

    def as_dict(self):
        return asdict(self)


def read_snapshot(path: str | Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ImportFailure("Cannot read a UTF-8 JSON snapshot") from None


def validate_snapshot(model, payload):
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_input=False, include_url=False):
            loc = list(error["loc"])
            if len(loc) > 1 and isinstance(loc[1], int):
                label = f"row {loc[1] + 1} ({'.'.join(map(str, loc[2:]))})"
            else:
                label = ".".join(map(str, loc)) or "snapshot"
            messages.append(f"{label}: {error['msg']}")
        raise ImportFailure("; ".join(messages)) from None


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _finish(session, callback, commit=True):
    try:
        result = callback()
        if commit:
            session.commit()
        return result
    except ImportFailure:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ImportFailure("Database rejected the import; no changes were saved") from None


def import_complexes(session: Session, payload, *, allow_clear_price=False, _commit=True) -> ImportReport:
    snapshot = validate_snapshot(ComplexSnapshot, payload)

    def apply():
        report = ImportReport()
        seen = set()
        for index, row in enumerate(snapshot.complexes, 1):
            if row.slug in seen:
                raise ImportFailure(f"row {index}: duplicate complex slug")
            seen.add(row.slug)
            current = session.scalar(select(ResidentialComplex).where(ResidentialComplex.slug == row.slug).with_for_update())
            values = row.model_dump()
            if current is None:
                session.add(ResidentialComplex(**values))
                report.created += 1
                continue
            price_fields = ("min_price_m2", "price_source_url", "price_observed_on", "price_checked_on")
            old_date, new_date = current.price_observed_on, row.price_observed_on
            if current.min_price_m2 is not None:
                if row.min_price_m2 is None:
                    if not allow_clear_price:
                        raise ImportFailure(f"row {index}: clearing a known price requires --allow-clear-price")
                elif old_date is not None and (new_date is None or new_date < old_date):
                    if row.min_price_m2 != current.min_price_m2 or row.price_source_url != current.price_source_url:
                        raise ImportFailure(f"row {index}: older or undated price conflicts with stored price; choose the source explicitly")
                    for key in price_fields:
                        values[key] = getattr(current, key)
                elif new_date == old_date and any(values[key] != getattr(current, key) for key in ("min_price_m2", "price_source_url")):
                    raise ImportFailure(f"row {index}: equal-date price sources conflict; choose the source explicitly")
            changed = any(getattr(current, key) != value for key, value in values.items())
            if changed:
                for key, value in values.items():
                    setattr(current, key, value)
                current.updated_at = utcnow()
                report.updated += 1
            else:
                report.unchanged += 1
        session.flush()
        return report
    return _finish(session, apply, _commit)


def import_lots(session: Session, payload, *, demo_mode=False, _commit=True) -> ImportReport:
    snapshot = validate_snapshot(LotSnapshot, payload)

    def apply():
        report = ImportReport()
        seen = set()
        for index, row in enumerate(snapshot.lots, 1):
            key = (row.complex_slug, row.external_id)
            if key in seen:
                raise ImportFailure(f"row {index}: duplicate apartment key")
            seen.add(key)
            if row.is_demo != demo_mode:
                raise ImportFailure(f"row {index}: apartment demo flag does not match database mode")
            complex_row = session.scalar(select(ResidentialComplex).where(ResidentialComplex.slug == row.complex_slug))
            if complex_row is None:
                raise ImportFailure(f"row {index}: unknown complex_slug")
            current = session.scalar(select(ApartmentLot).where(ApartmentLot.complex_id == complex_row.id, ApartmentLot.external_id == row.external_id).with_for_update())
            values = row.model_dump(exclude={"complex_slug"})
            values["complex_id"] = complex_row.id
            if current is None:
                session.add(ApartmentLot(**values, imported_at=utcnow()))
                report.created += 1
            elif row.updated_at < current.updated_at:
                report.unchanged += 1
            elif row.updated_at == current.updated_at:
                if any(getattr(current, key) != value for key, value in values.items()):
                    raise ImportFailure(f"row {index}: equal update time conflicts with stored apartment")
                report.unchanged += 1
            else:
                for key, value in values.items():
                    setattr(current, key, value)
                current.imported_at = utcnow()
                report.updated += 1
        session.flush()
        return report
    return _finish(session, apply, _commit)


def deactivate_lot(session: Session, complex_slug: str, external_id: str, *, _commit=True) -> ImportReport:
    def apply():
        current = session.scalar(select(ApartmentLot).join(ResidentialComplex).where(ResidentialComplex.slug == complex_slug, ApartmentLot.external_id == external_id).with_for_update())
        if current is None:
            raise ImportFailure("Apartment key was not found")
        if not current.is_active:
            return ImportReport(unchanged=1)
        current.is_active = False
        return ImportReport(updated=1)
    return _finish(session, apply, _commit)


def demo_seed(session: Session, *, demo_mode=False, _commit=True) -> ImportReport:
    if not demo_mode:
        raise ImportFailure("Demo generation requires the dedicated demo database")
    now = utcnow()
    complexes, lots = [], []
    for city_key, city in (("moscow", "Москва"), ("spb", "Санкт-Петербург"), ("sochi", "Сочи")):
        for number in range(1, 4):
            slug = f"demo-{city_key}-{number}"
            complexes.append(dict(slug=slug, city=city, name=f"Демо {city} {number}", developer="Демо застройщик", district="Демо район", housing_class="демо", min_price_m2=None, price_source_url=None, price_observed_on=None, price_checked_on=None, completion_status="needs_verification", completion_description="Вымышленные данные для демонстрации", completion_source_url="https://example.invalid/demo", completion_checked_on=now.date().isoformat(), notes="Синтетический объект"))
            for suffix, area, price, age, active in (("fresh", "50.00", str(7000000 + number * 100000), 0, True), ("expensive", "50.00", "99000000.00", 0, True), ("small", "20.00", "4000000.00", 0, True), ("old", "50.00", "6000000.00", 45, True), ("inactive", "50.00", "5000000.00", 0, False)):
                lots.append(dict(complex_slug=slug, external_id=f"demo-{suffix}", rooms=2, area_m2=area, starting_price_rub=price, updated_at=(now - timedelta(days=age)).isoformat() + "Z", source_url=None, building=None, is_active=active, is_demo=True))
    # Both phases share one transaction, including their validation failures.
    def apply():
        report = import_complexes(session, dict(schema_version=1, provenance="Синтетические данные", checked_on=now.date().isoformat(), complexes=complexes), _commit=False)
        lot_report = import_lots(session, dict(schema_version=1, lots=lots), demo_mode=True, _commit=False)
        return ImportReport(**{key: value + lot_report.as_dict()[key] for key, value in report.as_dict().items()})
    return _finish(session, apply)


