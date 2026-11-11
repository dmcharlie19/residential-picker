from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, DateTime, String, Text, UniqueConstraint
from app.models.types import ScaledDecimal
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ResidentialComplex(Base):
    __tablename__ = "residential_complexes"
    __table_args__ = (
        CheckConstraint("min_price_m2 IS NULL OR (typeof(min_price_m2) = 'integer' AND min_price_m2 BETWEEN 1 AND 99999999999999)", name="ck_complex_price"),
        CheckConstraint("completion_status IN ('completed','under_construction','mixed','needs_verification')", name="ck_completion_status"),
        Index("ix_complex_city_price", "city", "min_price_m2"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    city: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    developer: Mapped[str] = mapped_column(String(255))
    district: Mapped[str] = mapped_column(String(255))
    housing_class: Mapped[str] = mapped_column(String(32))
    min_price_m2: Mapped[Decimal | None] = mapped_column(ScaledDecimal(), nullable=True)
    price_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_observed_on: Mapped[date | None] = mapped_column(nullable=True)
    price_checked_on: Mapped[date | None] = mapped_column(nullable=True)
    completion_status: Mapped[str] = mapped_column(String(32))
    completion_description: Mapped[str] = mapped_column(Text)
    completion_source_url: Mapped[str] = mapped_column(Text)
    completion_checked_on: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ApartmentLot(Base):
    __tablename__ = "apartment_lots"
    __table_args__ = (
        UniqueConstraint("complex_id", "external_id", name="uq_lot_external"),
        CheckConstraint("rooms BETWEEN 0 AND 20", name="ck_lot_rooms"),
        CheckConstraint("typeof(area_m2) = 'integer' AND area_m2 BETWEEN 1 AND 99999999", name="ck_lot_area"),
        CheckConstraint("typeof(starting_price_rub) = 'integer' AND starting_price_rub BETWEEN 1 AND 9999999999999999", name="ck_lot_price"),
        Index("ix_lot_search", "complex_id", "is_active", "is_demo", "area_m2", "starting_price_rub"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey("residential_complexes.id", ondelete="RESTRICT"))
    external_id: Mapped[str] = mapped_column(String(150))
    rooms: Mapped[int] = mapped_column(Integer)
    area_m2: Mapped[Decimal] = mapped_column(ScaledDecimal())
    starting_price_rub: Mapped[Decimal] = mapped_column(ScaledDecimal())
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
