from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_FLOOR
from sqlalchemy import Integer, cast, exists, func, select
from sqlalchemy.orm import Session
from app.models import ApartmentLot as L, ResidentialComplex as C


def lots_statement(city, budget, area, now, tolerance, max_age, demo_mode):
    ranked = (
        select(L.id.label("lot_id"), func.row_number().over(
            partition_by=L.complex_id,
            order_by=(L.area_m2, L.updated_at.desc(), L.starting_price_rub, L.id),
        ).label("position"))
        .join(C, C.id == L.complex_id)
        .where(C.city == city, L.is_active.is_(True), L.is_demo.is_(demo_mode),
               cast(L.area_m2, Integer) >= int(area * 100),
               cast(L.area_m2, Integer) <= int((area * 100 * (Decimal("1") + tolerance)).to_integral_value(rounding=ROUND_FLOOR)),
               cast(L.starting_price_rub, Integer) <= int(budget * 100),
               L.updated_at >= now - timedelta(days=max_age), L.updated_at <= now)
        .subquery()
    )
    return (
        select(C, L).join(L, C.id == L.complex_id)
        .join(ranked, ranked.c.lot_id == L.id)
        .where(ranked.c.position == 1)
        .order_by(L.area_m2, L.updated_at.desc(), L.starting_price_rub, C.id, L.id)
        .limit(3)
    )


def find_lots(session: Session, **kwargs):
    return session.execute(lots_statement(**kwargs)).all()


def find_estimates(session: Session, *, city, budget, area, now, max_age, limit):
    total = func.estimate_cents(cast(C.min_price_m2, Integer), int(area * 100))
    cutoff = now - timedelta(days=max_age)
    first_date = cutoff.date() + (timedelta(days=1) if cutoff.time() != time() else timedelta())
    any_real_lot = exists(select(L.id).where(L.complex_id == C.id, L.is_demo.is_(False)))
    statement = (
        select(C).where(
            C.city == city, ~any_real_lot, C.min_price_m2.is_not(None),
            C.price_observed_on.is_not(None),
            C.price_observed_on >= first_date,
            C.price_observed_on <= now.date(), total <= int(budget * 100),
        ).order_by(total, C.id).limit(limit)
    )
    return session.scalars(statement).all()
