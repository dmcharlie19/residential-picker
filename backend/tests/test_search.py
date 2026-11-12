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
CONFIG = SimpleNamespace(demo_mode=False, price_max_age_days=30)


def query(budget="20000000", rooms=(0,1,2,3,4), city="Сочи"):
    return SearchQuery(city=city, budget_rub=Decimal(budget), rooms=list(rooms))

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


@pytest.mark.parametrize("demo,url", [
    (True,"sqlite:///catalog.sqlite3"),
    (False,"sqlite:///catalog-demo.sqlite3"),
])
def test_database_modes_cannot_mix(demo,url):
    with pytest.raises(ValueError):
        Settings(database_url=url,demo_mode=demo)


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


def test_all_matching_complexes_returned_in_stable_order(db_session):
    complexes=[complex_row(db_session,str(i)) for i in range(5)]
    for c in reversed(complexes):
        lot_row(db_session,c,"b",area_m2=Decimal("51"))
        lot_row(db_session,c,"a",area_m2=Decimal("50"))
    first=search(db_session,query(),now=NOW,config=CONFIG)
    second=search(db_session,query(),now=NOW,config=CONFIG)
    assert first.model_dump()==second.model_dump()
    assert [r.complex.id for r in first.results]==[c.id for c in complexes]


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
    assert "CHECK constraint failed" in str(rejected.value.orig)
    db_session.rollback()


def test_window_query_uses_bounded_selects_on_ten_thousand_lots(db_session,database_engine):
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
    event.listen(database_engine,"before_cursor_execute",capture)
    try:
        r=search(db_session,query(),now=NOW,config=CONFIG)
    finally:
        event.remove(database_engine,"before_cursor_execute",capture)
    assert r.count==100 and len(statements)<=3
    stmt=lots_statement(city="Сочи",budget=Decimal("20000000"),rooms=[0,1,2,3,4],
                        now=NOW,max_age=30,demo_mode=False)
    compiled=stmt.compile(database_engine,compile_kwargs={"literal_binds":True})
    plan=db_session.execute(text("EXPLAIN QUERY PLAN "+str(compiled))).mappings().all()
    assert any("INDEX" in row["detail"] for row in plan)


@pytest.fixture
def client(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db]=override
    with TestClient(app,raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def test_api_database_failure_is_not_empty_success(client,monkeypatch):
    import app.api.search as module
    def unavailable(*args,**kwargs):
        raise OperationalError("secret SQL",{},Exception("secret password"))
    monkeypatch.setattr(module,"search",unavailable)
    r=client.get("/api/v1/search",params=dict(city="Сочи",budget="1",rooms="1"))
    assert r.status_code==503
    assert "secret" not in r.text and r.json()["error"]["fields"]=={}


@pytest.mark.parametrize("kind", ["duplicate-slug", "duplicate-lot", "foreign-key", "rooms"])
def test_sqlite_rejects_invalid_relationships_and_duplicates(db_session, kind):
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


def test_maximum_price_preserves_every_kopeck(db_session):
    c=complex_row(db_session)
    lot=lot_row(db_session,c,starting_price_rub=Decimal("99999999999999.99"))
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(L,lot.id).starting_price_rub==Decimal("99999999999999.99")
    assert search(db_session,query(budget="99999999999999.98"),now=NOW,config=CONFIG).count==0
    assert search(db_session,query(budget="99999999999999.99"),now=NOW,config=CONFIG).count==1


@pytest.mark.parametrize("url",["sqlite://", "sqlite:///:memory:", "sqlite:///file:test?mode=memory&uri=true", "mysql+pymysql://x@localhost/catalog"])
def test_only_file_backed_sqlite_allowed(url):
    with pytest.raises(ValueError):
        Settings(database_url=url,demo_mode=False)


def test_raw_database_uses_square_metres_and_rubles(db_session):
    c=complex_row(db_session)
    lot=lot_row(db_session,c,area_m2=Decimal("23.10"),starting_price_rub=Decimal("7530600.01"))
    row=db_session.execute(text("SELECT area_m2, typeof(area_m2) AS area_type, starting_price_rub FROM apartment_lots WHERE id=:id"),{"id":lot.id}).mappings().one()
    assert row["area_m2"]==23.1
    assert row["area_type"]=="real"
    assert row["starting_price_rub"]=="7530600.01"


def test_price_order_is_numeric_not_lexicographic(db_session):
    for name,price in [("expensive","10000000.00"),("cheaper","9000000.00")]:
        c=complex_row(db_session,name)
        lot_row(db_session,c,starting_price_rub=Decimal(price))
    found=search(db_session,query(),now=NOW,config=CONFIG)
    assert [r.complex.name for r in found.results]==["cheaper","expensive"]



@pytest.mark.parametrize("field,value",[("budget","0"),("budget","-1"),("budget","NaN"),("budget","Infinity"),("budget","1e7"),("budget","1.001"),("budget","100000000000000"),("city",""),("city","x"*101),("rooms",""),("rooms","-1"),("rooms","5"),("rooms","1.0"),("rooms","1,2")])
def test_query_validation(field,value):
    params=dict(city="Сочи",budget="20000000",rooms="1")
    params[field]=value
    with pytest.raises(SearchValidationError): SearchQuery.from_params(list(params.items()))

def test_multiselect_params_normalize_and_reject_removed_area():
    params=[("city"," спб "),("budget","99999999999999.99"),("rooms","2"),("rooms","1"),("rooms","2")]
    q=SearchQuery.from_params(params)
    assert q.city=="Санкт-Петербург" and q.rooms==[1,2]
    for extra in [[("area","50")],[("limit","3")],[("city","Сочи")],[("budget","1")]]:
        with pytest.raises(SearchValidationError): SearchQuery.from_params(params+extra)
    with pytest.raises(SearchValidationError): SearchQuery.from_params(params[:2])

def test_rooms_union_studios_and_four_plus(db_session):
    for rooms in [0,1,2,3,4,5]:
        c=complex_row(db_session,str(rooms))
        lot_row(db_session,c,rooms=rooms,area_m2=Decimal("20")+rooms*30)
    assert [r.lot.rooms for r in search(db_session,query(rooms=[0,2]),now=NOW,config=CONFIG).results]==[0,2]
    assert [r.lot.rooms for r in search(db_session,query(rooms=[4]),now=NOW,config=CONFIG).results]==[4,5]

def test_cheapest_matching_lot_per_complex_and_global_price_order(db_session):
    a=complex_row(db_session,"a")
    lot_row(db_session,a,"wrong",rooms=3,starting_price_rub=Decimal("1"))
    lot_row(db_session,a,"expensive",rooms=1,starting_price_rub=Decimal("10000000"),area_m2=Decimal("20"))
    best=lot_row(db_session,a,"cheap",rooms=2,starting_price_rub=Decimal("9000000"),area_m2=Decimal("200"),updated_at=NOW-timedelta(days=1))
    for name,price in [("b","8000000"),("c","20000000"),("d","20000000.01")]:
        c=complex_row(db_session,name)
        lot_row(db_session,c,rooms=2,starting_price_rub=Decimal(price))
    r=search(db_session,query(rooms=[1,2]),now=NOW,config=CONFIG)
    assert [x.complex.name for x in r.results]==["b","a","c"]
    assert r.results[1].lot.id==best.id
    assert [x.estimated_price_rub for x in r.results]==["8000000.00","9000000.00","20000000.00"]

def test_no_estimate_without_specific_room_count(db_session):
    complex_row(db_session,"estimate",min_price_m2=Decimal("1"),price_observed_on=NOW.date())
    assert search(db_session,query(),now=NOW,config=CONFIG).results==[]
    assert search(db_session,query(city="Казань"),now=NOW,config=CONFIG).results==[]

def test_api_room_multiselect_and_price_order(client,db_session):
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    for name,rooms,price in [("expensive",1,"10000000"),("cheap",2,"9000000"),("wrong",3,"1")]:
        c=complex_row(db_session,name)
        lot_row(db_session,c,rooms=rooms,starting_price_rub=Decimal(price),updated_at=now)
    r=client.get("/api/v1/search",params=[("city","Сочи"),("budget","20000000"),("rooms","1"),("rooms","2")])
    assert r.status_code==200
    data=r.json()
    assert data["query"]["rooms"]==[1,2] and "desired_area_m2" not in data["query"]
    assert [x["complex"]["name"] for x in data["results"]]==["cheap","expensive"]
    assert data["results"][0]["lot"]["area_m2"]=="50.00"
    assert client.get("/api/v1/search?city=Сочи&budget=10&rooms=1&area=50").status_code==422
    assert client.get("/api/v1/search?city=Сочи&budget=10").status_code==422
    from app.api.search import router
    assert len(app.routes)==1 and [r.path for r in router.routes]==["/api/v1/search"]
