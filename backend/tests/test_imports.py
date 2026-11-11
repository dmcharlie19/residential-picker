import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import ApartmentLot, ResidentialComplex
from app.schemas.imports import LotSnapshot
from app.services.imports import ImportFailure, deactivate_lot, import_complexes, import_lots, read_snapshot


@pytest.fixture
def complex_snapshot():
    return read_snapshot(Path(__file__).resolve().parents[2] / "data" / "complexes.snapshot.json")


def lot_payload(slug="sochi-kislorod", **overrides):
    row = dict(complex_slug=slug, external_id="test-1", rooms=2, area_m2="50.25", starting_price_rub="7000000.01", updated_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), source_url="https://example.invalid/lot", building=None, is_active=True, is_demo=False)
    row.update(overrides)
    return dict(schema_version=1, lots=[row])


@pytest.mark.parametrize("changes", [dict(area_m2=50.2), dict(area_m2="1.001"), dict(area_m2="NaN"), dict(starting_price_rub="100000000000000.00"), dict(updated_at="2026-01-01T12:00:00"), dict(updated_at="2099-01-01"), dict(source_url="file:///tmp/lot"), dict(rooms=True), dict(extra="unknown")])
def test_lot_validation(changes):
    with pytest.raises(ValueError):
        LotSnapshot.model_validate(lot_payload(**changes))


def test_date_only_is_midnight_utc():
    row = LotSnapshot.model_validate(lot_payload(updated_at="2026-01-01")).lots[0]
    assert row.updated_at == datetime(2026, 1, 1)


def test_snapshot_idempotent_and_unknown_prices(db_session, complex_snapshot):
    assert import_complexes(db_session, complex_snapshot).created == 15
    assert import_complexes(db_session, complex_snapshot).unchanged == 15
    assert db_session.scalar(select(func.count()).select_from(ResidentialComplex)) == 15
    assert db_session.scalar(select(func.count()).select_from(ResidentialComplex).where(ResidentialComplex.min_price_m2.is_(None))) == 2


def test_unknown_complex_rolls_back_entire_import(db_session, complex_snapshot):
    import_complexes(db_session, complex_snapshot)
    payload = lot_payload()
    payload["lots"].append(lot_payload("missing")["lots"][0])
    with pytest.raises(ImportFailure, match="row 2"):
        import_lots(db_session, payload)
    assert db_session.scalar(select(func.count()).select_from(ApartmentLot)) == 0


def test_lot_stale_equal_conflict_and_deactivate(db_session, complex_snapshot):
    import_complexes(db_session, complex_snapshot)
    payload = lot_payload()
    assert import_lots(db_session, payload).created == 1
    current = db_session.scalar(select(ApartmentLot))
    imported = current.imported_at
    assert import_lots(db_session, payload).unchanged == 1
    stale = copy.deepcopy(payload)
    stale["lots"][0].update(updated_at="2020-01-01", starting_price_rub="1.00")
    assert import_lots(db_session, stale).unchanged == 1
    conflict = copy.deepcopy(payload)
    conflict["lots"][0]["starting_price_rub"] = "1.00"
    with pytest.raises(ImportFailure, match="equal update"):
        import_lots(db_session, conflict)
    db_session.refresh(current)
    assert str(current.starting_price_rub) == "7000000.01"
    assert current.imported_at == imported
    assert deactivate_lot(db_session, "sochi-kislorod", "test-1").updated == 1
    assert deactivate_lot(db_session, "sochi-kislorod", "test-1").unchanged == 1


def test_demo_and_duplicates_rejected(db_session, complex_snapshot):
    import_complexes(db_session, complex_snapshot)
    with pytest.raises(ImportFailure, match="demo flag"):
        import_lots(db_session, lot_payload(is_demo=True))
    payload = lot_payload()
    payload["lots"] *= 2
    with pytest.raises(ImportFailure, match="duplicate"):
        import_lots(db_session, payload)
    assert db_session.scalar(select(func.count()).select_from(ApartmentLot)) == 0


def test_dated_price_cannot_be_replaced_by_undated(db_session, complex_snapshot):
    snapshot = copy.deepcopy(complex_snapshot)
    snapshot["complexes"] = snapshot["complexes"][:1]
    snapshot["complexes"][0]["price_observed_on"] = "2026-11-01"
    import_complexes(db_session, snapshot)
    old = copy.deepcopy(snapshot)
    old["complexes"][0].update(price_observed_on=None, min_price_m2="1.00")
    with pytest.raises(ImportFailure, match="older or undated"):
        import_complexes(db_session, old)
    cleared = copy.deepcopy(snapshot)
    cleared["complexes"][0]["min_price_m2"] = None
    with pytest.raises(ImportFailure, match="allow-clear-price"):
        import_complexes(db_session, cleared)
    assert import_complexes(db_session, cleared, allow_clear_price=True).updated == 1


def test_equal_conflict_rolls_back_prior_new_row(db_session, complex_snapshot):
    import_complexes(db_session, complex_snapshot)
    payload = lot_payload()
    import_lots(db_session, payload)
    conflict = copy.deepcopy(payload["lots"][0])
    conflict["starting_price_rub"] = "1.00"
    fresh = copy.deepcopy(payload["lots"][0])
    fresh["external_id"] = "new-before-conflict"
    with pytest.raises(ImportFailure, match="row 2"):
        import_lots(db_session, dict(schema_version=1, lots=[fresh, conflict]))
    assert db_session.scalar(select(func.count()).select_from(ApartmentLot)) == 1
