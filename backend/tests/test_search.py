from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, insert, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.config import Settings
from app.db import get_db
from app.main import app
from app.models import ApartmentLot as L, ResidentialComplex as C
from app.repositories.search import lots_statement
from app.schemas.search import SearchQuery, SearchValidationError
from app.services.search import search

NOW = datetime(2026, 11, 11, 12)
CONFIG = SimpleNamespace(demo_mode=False, area_tolerance_ratio=Decimal(".10"), price_max_age_days=30)


def query(budget="20000000", area="50", city="Сочи"):
    return SearchQuery(city=city, budget_rub=Decimal(budget), desired_area_m2=Decimal(area))


def complex_row(s, slug="one", **kw):
    values = dict(slug=slug, city="Сочи", name=slug, developer="Застройщик", district="Район",
                  housing_class="бизнес", min_price_m2=None, price_source_url=None,
                  price_observed_on=None, price_checked_on=None,
                  completion_status="completed", completion_description="Сдан",
                  completion_source_url="https://example.com/ready", completion_checked_on=NOW.date())
    values.update(kw)
    row = C(**values)
    s.add(row)
    s.flush()
    return row


def lot_row(s, c, external_id="one", **kw):
    values = dict(complex_id=c.id, external_id=external_id, rooms=2, area_m2=Decimal("50"),
                  starting_price_rub=Decimal("15000000"), updated_at=NOW,
                  source_url=None, building=None, is_active=True, is_demo=False)
    values.update(kw)
    row = L(**values)
    s.add(row)
    s.flush()
    return row


@pytest.mark.parametrize("field,value", [
    ("budget","0"),("budget","-1"),("budget","NaN"),("budget","Infinity"),
    ("budget","1e7"),("budget","1.001"),("budget","100000000000000"),
    ("area","0"),("area","-1"),("area","1000000"),("area","50.001"),
    ("city",""),("city"," " * 4),("city","a"*101),
])
def test_query_rejects_invalid_numbers_and_city(field,value):
    pairs = dict(city="Сочи",budget="20000000",area="50")
    pairs[field]=value
    with pytest.raises(SearchValidationError):
        SearchQuery.from_params(list(pairs.items()))


def test_query_aliases_precision_duplicates_and_unknown():
    q = SearchQuery.from_params([("city"," спб "),("budget","99999999999999.99"),("area","50.25")])
    assert q.city == "Санкт-Петербург" and q.budget_rub == Decimal("99999999999999.99")
    for extra in ([("area","51")], [("limit","3")]):
        with pytest.raises(SearchValidationError):
            SearchQuery.from_params([("city","Сочи"),("budget","10"),("area","50")]+extra)


@pytest.mark.parametrize("demo,url", [
    (True,"mysql+pymysql://x@localhost/residential_picker"),
    (False,"mysql+pymysql://x@localhost/residential_picker_demo"),
])
def test_database_modes_cannot_mix(demo,url):
    with pytest.raises(ValueError):
        Settings(database_url=url,demo_mode=demo)


def test_budget_area_boundaries_and_best_per_complex(db_session):
    c = complex_row(db_session)
    lot_row(db_session,c,"over-budget",starting_price_rub=Decimal("20000000.01"))
    lot_row(db_session,c,"too-small",area_m2=Decimal("49.99"))
    lot_row(db_session,c,"too-big",area_m2=Decimal("55.01"))
    best = lot_row(db_session,c,"exact",starting_price_rub=Decimal("20000000"))
    lot_row(db_session,c,"upper",area_m2=Decimal("55"),starting_price_rub=Decimal("1"))
    found = search(db_session,query(),now=NOW,config=CONFIG)
    assert found.count == 1 and found.results[0].lot.id == best.id
    assert found.results[0].estimated_price_rub == "20000000.00"
    assert "INSUFFICIENT_MATCHES" in found.warnings


def test_upper_area_boundary_is_inclusive(db_session):
    c=complex_row(db_session)
    lot_row(db_session,c,area_m2=Decimal("55"))
    assert search(db_session,query(),now=NOW,config=CONFIG).count==1


def test_freshness_boundary_inactive_future_and_demo(db_session):
    ids=[]
    for index, changes in enumerate((
        dict(updated_at=NOW-timedelta(days=30)),
        dict(updated_at=NOW-timedelta(days=30,microseconds=1)),
        dict(updated_at=NOW+timedelta(microseconds=1)),
        dict(is_active=False),dict(is_demo=True),
    )):
        c=complex_row(db_session,str(index))
        lot_row(db_session,c,**changes)
        ids.append(c.id)
    response=search(db_session,query(),now=NOW,config=CONFIG)
    assert [r.complex.id for r in response.results]==ids[:1]


def test_stable_ranking_three_distinct_complexes(db_session):
    complexes=[complex_row(db_session,str(i)) for i in range(5)]
    for c in reversed(complexes):
        lot_row(db_session,c,"b",area_m2=Decimal("51"))
        lot_row(db_session,c,"a",area_m2=Decimal("50"))
    first=search(db_session,query(),now=NOW,config=CONFIG)
    second=search(db_session,query(),now=NOW,config=CONFIG)
    assert first.model_dump()==second.model_dump()
    assert [r.complex.id for r in first.results]==[c.id for c in complexes[:3]]


def test_closest_then_newest_then_cheapest(db_session):
    a=complex_row(db_session,"a")
    b=complex_row(db_session,"b")
    c=complex_row(db_session,"c")
    lot_row(db_session,a,area_m2=Decimal("51"),starting_price_rub=Decimal("1"))
    lot_row(db_session,b,updated_at=NOW-timedelta(days=1),starting_price_rub=Decimal("1"))
    lot_row(db_session,c,starting_price_rub=Decimal("19000000"))
    r=search(db_session,query(),now=NOW,config=CONFIG)
    assert [m.complex.name for m in r.results]==["c","b","a"]


def test_estimates_rounding_and_no_substitution_for_historical_lots(db_session):
    fresh=NOW.date()
    c=complex_row(db_session,"estimate",min_price_m2=Decimal("100000.01"),price_observed_on=fresh)
    historic=complex_row(db_session,"historic",min_price_m2=Decimal("1"),price_observed_on=fresh)
    lot_row(db_session,historic,is_active=False)
    complex_row(db_session,"unknown-date",min_price_m2=Decimal("1"))
    complex_row(db_session,"old",min_price_m2=Decimal("1"),price_observed_on=fresh-timedelta(days=31))
    complex_row(db_session,"future",min_price_m2=Decimal("1"),price_observed_on=fresh+timedelta(days=1))
    r=search(db_session,query(area="50.25",budget="5025000.49"),now=NOW,config=CONFIG)
    assert r.count==0
    r=search(db_session,query(area="50.25",budget="5025000.51"),now=NOW,config=CONFIG)
    assert r.count==1 and r.results[0].match_type=="estimate"
    assert r.results[0].lot is None and r.results[0].estimated_price_rub=="5025000.50"
    # 100000.01 * 50.25 = 5025000.5025 rounds to .50; exact budget also qualifies.
    assert search(db_session,query(area="50.25",budget="5025000.50"),now=NOW,config=CONFIG).count==1


def test_real_lots_before_cheaper_estimates_and_unknown_city(db_session):
    e=complex_row(db_session,"estimate",min_price_m2=Decimal("1"),price_observed_on=NOW.date())
    c=complex_row(db_session,"lot")
    lot_row(db_session,c)
    r=search(db_session,query(),now=NOW,config=CONFIG)
    assert [m.match_type for m in r.results]==["lot","estimate"]
    assert search(db_session,query(city="Казань"),now=NOW,config=CONFIG).results==[]


def test_demo_mode_only_returns_demo_lots(db_session):
    c=complex_row(db_session)
    lot_row(db_session,c,"real")
    demo=lot_row(db_session,c,"demo",is_demo=True)
    config=SimpleNamespace(**{**vars(CONFIG),"demo_mode":True})
    r=search(db_session,query(),now=NOW,config=config)
    assert r.demo_mode and r.results[0].lot.id==demo.id
    assert r.results[0].warnings==["DEMO_DATA"] and "DEMO_DATA" in r.warnings


def test_db_constraints_and_cyrillic_decimal(db_session):
    c=complex_row(db_session)
    lot=lot_row(db_session,c,starting_price_rub=Decimal("1234567.89"))
    db_session.commit()
    db_session.refresh(lot)
    assert lot.starting_price_rub==Decimal("1234567.89")
    assert c.developer=="Застройщик"
    db_session.add(L(complex_id=c.id,external_id="bad",rooms=2,area_m2=0,
                     starting_price_rub=1,updated_at=NOW,is_active=True,is_demo=False))
    with pytest.raises((IntegrityError, OperationalError)) as rejected:
        db_session.commit()
    assert rejected.value.orig.args[0] == 3819
    db_session.rollback()


def test_window_query_uses_bounded_selects_on_ten_thousand_lots(db_session,mysql_engine):
    complexes=[complex_row(db_session,f"scale-{i}") for i in range(100)]
    data=[dict(complex_id=c.id,external_id=f"lot-{j}",rooms=2,area_m2=Decimal("50")+Decimal(j)/100,
               starting_price_rub=10000000+j,updated_at=NOW,is_active=True,is_demo=False,imported_at=NOW)
          for c in complexes for j in range(100)]
    db_session.execute(insert(L),data)
    db_session.commit()
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(mysql_engine,"before_cursor_execute",capture)
    try:
        r=search(db_session,query(),now=NOW,config=CONFIG)
    finally:
        event.remove(mysql_engine,"before_cursor_execute",capture)
    assert r.count==3 and len(statements)<=3
    stmt=lots_statement(city="Сочи",budget=Decimal("20000000"),area=Decimal("50"),
                        now=NOW,tolerance=Decimal(".10"),max_age=30,demo_mode=False)
    compiled=stmt.compile(mysql_engine,compile_kwargs={"literal_binds":True})
    plan=db_session.execute(text("EXPLAIN "+str(compiled))).mappings().all()
    assert any(row["key"] for row in plan if row["table"] in ("residential_complexes","apartment_lots"))


@pytest.fixture
def client(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db]=override
    with TestClient(app,raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def test_api_response_empty_validation_and_single_route(client):
    response=client.get("/api/v1/search",params=dict(city=" СПб ",budget="20000000",area="50"))
    assert response.status_code==200
    data=response.json()
    assert data["query"]["city"]=="Санкт-Петербург"
    assert data["results"]==[] and data["count"]==0
    assert data["query"]["budget_rub"]=="20000000.00"
    bad=client.get("/api/v1/search?city=Сочи&budget=10&area=50&area=51")
    assert bad.status_code==422 and "area" in bad.json()["error"]["fields"]
    assert client.get("/api/v1/search?city=Сочи&budget=10&area=50&limit=3").status_code==422
    from app.api.search import router
    assert len(app.routes)==1
    assert [r.path for r in router.routes]==["/api/v1/search"]
    assert client.get("/docs").status_code==404


def test_api_lot_and_estimate_contract(client,db_session):
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    c=complex_row(db_session)
    lot_row(db_session,c,updated_at=now,starting_price_rub=Decimal("15000000.01"))
    complex_row(db_session,"estimate",min_price_m2=Decimal("100000"),price_observed_on=now.date())
    response=client.get("/api/v1/search",params=dict(city="Сочи",budget="20000000",area="50"))
    assert response.status_code==200
    r=response.json()
    assert r["count"]==2 and r["results"][0]["lot"]["starting_price_rub"]=="15000000.01"
    assert r["results"][1]["match_type"]=="estimate" and r["results"][1]["lot"] is None
    assert r["results"][0]["lot"]["updated_at"].endswith("Z")


def test_api_database_failure_is_not_empty_success(client,monkeypatch):
    import app.api.search as module
    def unavailable(*args,**kwargs):
        raise OperationalError("secret SQL",{},Exception("secret password"))
    monkeypatch.setattr(module,"search",unavailable)
    r=client.get("/api/v1/search",params=dict(city="Сочи",budget="1",area="1"))
    assert r.status_code==503
    assert "secret" not in r.text and r.json()["error"]["fields"]=={}


@pytest.mark.parametrize("kind", ["duplicate-slug", "duplicate-lot", "foreign-key", "rooms"])
def test_mysql_rejects_invalid_relationships_and_duplicates(db_session, kind):
    c=complex_row(db_session)
    lot_row(db_session,c)
    db_session.commit()
    with pytest.raises((IntegrityError, OperationalError)):
        if kind == "duplicate-slug":
            complex_row(db_session)
        elif kind == "duplicate-lot":
            lot_row(db_session,c)
        elif kind == "foreign-key":
            lot_row(db_session,c,"orphan",complex_id=999999999)
        else:
            lot_row(db_session,c,"rooms",rooms=21)
        db_session.flush()
    db_session.rollback()


def test_complex_import_rejects_future_date():
    import json
    from pathlib import Path
    from app.schemas.imports import ComplexSnapshot
    complex_snapshot=json.loads((Path(__file__).resolve().parents[2]/"data/complexes.snapshot.json").read_text(encoding="utf-8"))
    payload={**complex_snapshot, "complexes":[{**complex_snapshot["complexes"][0],"price_observed_on":"2099-01-01"}]}
    with pytest.raises(ValueError):
        ComplexSnapshot.model_validate(payload)
