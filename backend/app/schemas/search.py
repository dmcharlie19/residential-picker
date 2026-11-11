import re
from decimal import Decimal
from pydantic import BaseModel
from typing import Literal


class SearchValidationError(ValueError):
    def __init__(self, fields):
        self.fields = fields


class SearchQuery(BaseModel):
    city: str
    budget_rub: Decimal
    desired_area_m2: Decimal

    @classmethod
    def from_params(cls, pairs):
        values = {}
        errors = {}
        allowed = {"city", "budget", "area"}
        for key, value in pairs:
            if key not in allowed:
                errors[key] = ["Неизвестный параметр"]
            elif key in values:
                errors[key] = ["Параметр указан несколько раз"]
            else:
                values[key] = value
        for key in allowed - values.keys():
            errors[key] = ["Обязательное поле"]
        city = values.get("city", "").strip()
        if "city" in values and not 1 <= len(city) <= 100:
            errors["city"] = ["Введите город длиной от 1 до 100 символов"]
        parsed = {}
        for field, maximum in (("budget", Decimal("99999999999999.99")), ("area", Decimal("999999.99"))):
            if field not in values:
                continue
            raw = values[field]
            if len(raw) > 40 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw):
                errors[field] = ["Введите положительное число, не более двух знаков после точки"]
                continue
            number = Decimal(raw)
            if number <= 0 or number > maximum:
                errors[field] = ["Значение вне допустимого диапазона"]
            else:
                parsed[field] = number
        if errors:
            raise SearchValidationError(errors)
        aliases = {"москва": "Москва", "сочи": "Сочи", "спб": "Санкт-Петербург",
                   "санкт петербург": "Санкт-Петербург", "санкт-петербург": "Санкт-Петербург"}
        city = aliases.get(city.casefold(), city)
        return cls(city=city, budget_rub=parsed["budget"], desired_area_m2=parsed["area"])


class ComplexResponse(BaseModel):
    id: int
    name: str
    city: str
    developer: str
    district: str
    housing_class: str
    completion_status: str
    completion_description: str
    completion_source_url: str | None


class LotResponse(BaseModel):
    id: int
    rooms: int
    area_m2: str
    starting_price_rub: str
    updated_at: str
    source_url: str | None
    building: str | None
    is_demo: bool


class MatchResponse(BaseModel):
    complex: ComplexResponse
    match_type: Literal["lot", "estimate"]
    lot: LotResponse | None
    matched_area_m2: str
    estimated_price_rub: str
    price_source_url: str | None
    price_observed_on: str | None
    warnings: list[str]


class QueryResponse(BaseModel):
    city: str
    budget_rub: str
    desired_area_m2: str


class SearchResponse(BaseModel):
    query: QueryResponse
    generated_at: str
    demo_mode: bool
    count: int
    results: list[MatchResponse]
    warnings: list[str]
