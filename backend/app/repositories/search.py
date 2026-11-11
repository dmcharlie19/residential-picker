from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import exists, func, select
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
               L.area_m2 >= area, L.area_m2 <= area * (Decimal("1") + tolerance),
               L.starting_price_rub <= budget,
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
    total = func.round(C.min_price_m2 * area, 2)
    any_real_lot = exists(select(L.id).where(L.complex_id == C.id, L.is_demo.is_(False)))
    statement = (
        select(C).where(
            C.city == city, ~any_real_lot, C.min_price_m2.is_not(None),
            C.price_observed_on.is_not(None),
            func.timestamp(C.price_observed_on) >= now - timedelta(days=max_age),
            func.timestamp(C.price_observed_on) <= now, total <= budget,
        ).order_by(total, C.id).limit(limit)
    )
    return session.scalars(statement).all()
