from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.config import settings
from app.repositories.search import find_lots
from app.schemas.search import ComplexResponse, LotResponse, MatchResponse, QueryResponse, SearchQuery, SearchResponse


def money(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def iso_utc(value):
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat() + "Z"


def complex_response(c):
    return ComplexResponse(**{key: getattr(c, key) for key in ComplexResponse.model_fields})


def search(session: Session, query: SearchQuery, *, now=None, config=None) -> SearchResponse:
    config = config or settings
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    matches = []
    rows = find_lots(
        session, city=query.city, budget=query.budget_rub, rooms=query.rooms,
        now=now, max_age=config.price_max_age_days,
        demo_mode=config.demo_mode,
    )
    for c, lot in rows:
        matches.append(MatchResponse(
            complex=complex_response(c), match_type="lot",
            lot=LotResponse(id=lot.id, rooms=lot.rooms, area_m2=money(lot.area_m2),
                            starting_price_rub=money(lot.starting_price_rub),
                            updated_at=iso_utc(lot.updated_at), source_url=lot.source_url,
                            building=lot.building, is_demo=lot.is_demo),
            matched_area_m2=money(lot.area_m2), estimated_price_rub=money(lot.starting_price_rub),
            price_source_url=lot.source_url, price_observed_on=lot.updated_at.date().isoformat(),
            warnings=["DEMO_DATA"] if config.demo_mode else [],
        ))
    warnings = []
    if config.demo_mode:
        warnings.append("DEMO_DATA")
    return SearchResponse(
        query=QueryResponse(city=query.city, budget_rub=money(query.budget_rub),
                            rooms=query.rooms),
        generated_at=iso_utc(now), demo_mode=config.demo_mode,
        count=len(matches), results=matches, warnings=warnings,
    )
