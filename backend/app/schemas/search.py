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
    rooms: list[Literal[0, 1, 2, 3, 4]]

    @classmethod
    def from_params(cls, pairs):
        values, errors, room_values = {}, {}, []
        for key, value in pairs:
            if key == "rooms":
                room_values.append(value)
            elif key not in {"city", "budget"}:
                errors[key] = ["Неизвестный параметр"]
            elif key in values:
                errors[key] = ["Параметр указан несколько раз"]
            else:
                values[key] = value
        for key in {"city", "budget"} - values.keys():
            errors[key] = ["Обязательное поле"]
        city = values.get("city", "").strip()
        if "city" in values and not 1 <= len(city) <= 100:
            errors["city"] = ["Введите город длиной от 1 до 100 символов"]
        budget = Decimal(0)
        if "budget" in values:
            raw = values["budget"]
            if len(raw) > 40 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw):
                errors["budget"] = ["Введите положительное число, не более двух знаков после точки"]
            else:
                budget = Decimal(raw)
                if not 0 < budget <= Decimal("99999999999999.99"):
                    errors["budget"] = ["Значение вне допустимого диапазона"]
        if not room_values or any(value not in {"0", "1", "2", "3", "4"} for value in room_values):
            errors["rooms"] = ["Выберите комнаты: студия, 1, 2, 3 или 4+; можно несколько"]
        if errors:
            raise SearchValidationError(errors)
        aliases = {"москва": "Москва", "сочи": "Сочи", "спб": "Санкт-Петербург",
                   "санкт петербург": "Санкт-Петербург", "санкт-петербург": "Санкт-Петербург"}
        return cls(city=aliases.get(city.casefold(), city), budget_rub=budget,
                   rooms=sorted({int(value) for value in room_values}))


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
    rooms: list[int]


class SearchResponse(BaseModel):
    query: QueryResponse
    generated_at: str
    demo_mode: bool
    count: int
    results: list[MatchResponse]
    warnings: list[str]
