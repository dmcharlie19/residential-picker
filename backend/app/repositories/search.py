from datetime import timedelta
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session
from app.models import ApartmentLot as L, ResidentialComplex as C

def lots_statement(city, budget, rooms, now, max_age, demo_mode):
    price = func.decimal_cents(L.starting_price_rub)
    exact_rooms = [number for number in rooms if number < 4]
    room_filter = or_(L.rooms.in_(exact_rooms), L.rooms >= 4 if 4 in rooms else false())
    ranked = (
        select(L.id.label("lot_id"), func.row_number().over(
            partition_by=L.complex_id,
            order_by=(price, L.updated_at.desc(), L.id),
        ).label("position"))
        .join(C, C.id == L.complex_id)
        .where(C.city == city, L.is_active.is_(True), L.is_demo.is_(demo_mode),
               room_filter, price <= int(budget * 100),
               L.updated_at >= now - timedelta(days=max_age), L.updated_at <= now)
        .subquery()
    )
    return (
        select(C, L).join(L, C.id == L.complex_id)
        .join(ranked, ranked.c.lot_id == L.id)
        .where(ranked.c.position == 1)
        .order_by(price, L.updated_at.desc(), C.id, L.id)
    )

def find_lots(session: Session, **kwargs):
    return session.execute(lots_statement(**kwargs)).all()
