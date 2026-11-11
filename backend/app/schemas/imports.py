from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, field_validator


def decimal_string(value, precision):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value):
        raise ValueError("expected a positive decimal string with at most two fractional digits")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid decimal")
    if not number.is_finite() or number <= 0 or number >= Decimal(10) ** (precision - 2):
        raise ValueError("decimal outside database range")
    return number


PriceM2 = Annotated[Decimal, BeforeValidator(lambda value: decimal_string(value, 14))]
Area = Annotated[Decimal, BeforeValidator(lambda value: decimal_string(value, 8))]
Price = Annotated[Decimal, BeforeValidator(lambda value: decimal_string(value, 16))]


class ImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def valid_urls(cls, value, info):
        if info.field_name.endswith("_url") and value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("source URL must use http or https")
        return value


class ComplexRow(ImportRow):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    city: Literal["Сочи", "Москва", "Санкт-Петербург"]
    name: str = Field(min_length=1, max_length=200)
    developer: str = Field(min_length=1, max_length=255)
    district: str = Field(min_length=1, max_length=255)
    housing_class: str = Field(min_length=1, max_length=32)
    min_price_m2: PriceM2 | None
    price_source_url: str | None
    price_observed_on: date | None
    price_checked_on: date | None
    completion_status: Literal["completed", "under_construction", "mixed", "needs_verification"]
    completion_description: str = Field(min_length=1)
    completion_source_url: str = Field(min_length=1)
    completion_checked_on: date
    notes: str | None

    @field_validator("price_observed_on", "price_checked_on", "completion_checked_on")
    @classmethod
    def no_future_date(cls, value):
        if value is not None and value > datetime.now(timezone.utc).date():
            raise ValueError("source date cannot be in the future")
        return value


class ComplexSnapshot(ImportRow):
    schema_version: Literal[1]
    provenance: str
    checked_on: date
    complexes: list[ComplexRow]


class LotRow(ImportRow):
    complex_slug: str = Field(min_length=1, max_length=100)
    external_id: str = Field(min_length=1, max_length=150)
    rooms: Annotated[StrictInt, Field(ge=0, le=20)]
    area_m2: Area
    starting_price_rub: Price
    updated_at: datetime
    source_url: str | None
    building: str | None = Field(max_length=100)
    is_active: StrictBool
    is_demo: StrictBool

    @field_validator("updated_at", mode="before")
    @classmethod
    def source_time(cls, value):
        if not isinstance(value, str):
            raise ValueError("source time must be an ISO date or timezone-qualified datetime")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            stamp = datetime.combine(date.fromisoformat(value), time(), timezone.utc)
        else:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("source datetime requires timezone")
        stamp = stamp.astimezone(timezone.utc)
        if stamp > datetime.now(timezone.utc):
            raise ValueError("source update cannot be in the future")
        return stamp.replace(tzinfo=None)


class LotSnapshot(ImportRow):
    schema_version: Literal[1]
    lots: list[LotRow]
