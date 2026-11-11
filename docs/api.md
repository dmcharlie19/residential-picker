# Контракт API v1

Единственный прикладной endpoint: GET /api/v1/search.

## Query

- city: строка, обязательна, после trim 1..100 символов. Регистр незначим. Известные варианты «СПб», «Санкт Петербург», «Санкт-Петербург» приводятся к «Санкт-Петербург»; «Москва» и «Сочи» — канонически. Непустой неизвестный город возвращает 200 с пустым списком.
- budget: положительная десятичная строка в рублях, максимум 99999999999999.99, до 2 знаков после точки.
- area: положительная десятичная строка в м², максимум 999999.99, до 2 знаков после точки.
- limit клиент не задаёт: максимум 3 фиксирован на backend.
- Неизвестные query-параметры отвергать 422, повторяющиеся обязательные параметры — 422.

Пример: /api/v1/search?city=Сочи&budget=20000000&area=50

## 200 — типовая структура

```json
{
  "query": {"city": "Сочи", "budget_rub": "20000000.00", "desired_area_m2": "50.00"},
  "generated_at": "2026-11-11T12:00:00Z",
  "demo_mode": false,
  "count": 1,
  "results": [{
    "complex": {
      "id": 101,
      "name": "Тестовый ЖК",
      "city": "Сочи",
      "developer": "Тестовый застройщик",
      "district": "Центральный",
      "housing_class": "бизнес",
      "completion_status": "under_construction",
      "completion_description": "IV кв. 2028",
      "completion_source_url": "https://example.com/completion"
    },
    "match_type": "lot",
    "lot": {
      "id": 501,
      "rooms": 2,
      "area_m2": "51.00",
      "starting_price_rub": "18000000.00",
      "updated_at": "2026-11-10T10:00:00Z",
      "source_url": "https://example.com/lot",
      "building": "1",
      "is_demo": false
    },
    "matched_area_m2": "51.00",
    "estimated_price_rub": "18000000.00",
    "price_source_url": "https://example.com/lot",
    "price_observed_on": "2026-11-10",
    "warnings": []
  }],
  "warnings": []
}
```

Пример выше синтетический, только иллюстрирует контракт, не является рыночной квартирой.

match_type = lot | estimate. Для estimate lot=null, matched_area_m2=желаемой площади, estimated_price_rub=расчёту; warnings содержит ESTIMATED_PRICE. Название estimated_price_rub одинаково для карточек, но при lot это опубликованная стартовая цена квартиры. UI показывает точный смысл по match_type.

Для lot price_observed_on = UTC-дата lot.updated_at; для estimate — дата цены ЖК. Суммы и площади сериализуются строками с двумя знаками после точки; даты-время — ISO 8601 UTC с Z. Ссылки NULL разрешены и не превращаются в неработающие кнопки. Ссылки в UI активировать только для http/https.

При 0..2 результатах top-level warnings содержит INSUFFICIENT_MATCHES. При 0 results=[]; count всегда равен длине массива. В DEMO_MODE top-level и карточки предупреждают DEMO_DATA.

## Ошибки

- 422: отсутствует параметр, отрицательное/нулевое/нечисловое значение, NaN/Infinity, лишняя точность, переполнение, пустой город, повторы/неизвестные параметры.
- 503: БД недоступна.
- 500: непредвиденная ошибка, без SQL/секретов в ответе.

Единый формат: {"error":{"code":"VALIDATION_ERROR","message":"Проверьте параметры поиска","fields":{"budget":["Введите положительное число"]}}}.
Для 503/500 fields={}. Невалидный запрос проверяется до запроса в БД. CORS/proxy не добавляют прикладных маршрутов; сервер может обрабатывать технический OPTIONS.
