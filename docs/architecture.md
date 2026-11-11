# Архитектура

## Компоненты

Браузер → frontend React/Vite → GET /api/v1/search → FastAPI → MySQL.

В production frontend и /api обслуживаются под одним origin через reverse proxy; Vite используется для разработки и сборки. В разработке Vite proxy перенаправляет /api на backend. Backend хранит настройки в environment; DATABASE_URL не передаётся в frontend.

Структура реализации:
- backend/app/api/search.py — HTTP-слой.
- backend/app/schemas/search.py — валидация запроса и ответа.
- backend/app/models/ — ORM-модели.
- backend/app/services/search.py — правила выбора.
- backend/app/repositories/search.py — пакетные SQL-запросы.
- backend/app/cli.py — импорт и обновление.
- backend/alembic/ — миграции.
- backend/tests/ — unit и интеграционные тесты с MySQL.
- frontend/src/App.tsx — форма и результаты.
- frontend/src/api.ts — клиент контракта и десятичное форматирование.
- frontend/tests/ — компонентные и браузерные сценарии.
- compose.yaml — MySQL, backend, frontend для локального запуска.

## residential_complexes — главная таблица

- id BIGINT UNSIGNED PK.
- slug VARCHAR(100) NOT NULL UNIQUE — стабильный ключ импорта, не вычислять заново при переименовании.
- city VARCHAR(100) NOT NULL — один из трёх канонических городов MVP.
- name VARCHAR(200) NOT NULL.
- developer VARCHAR(255) NOT NULL.
- district VARCHAR(255) NOT NULL.
- housing_class VARCHAR(32) NOT NULL.
- min_price_m2 DECIMAL(14,2) NULL, CHECK > 0 когда не NULL.
- price_source_url TEXT NULL; price_observed_on DATE NULL; price_checked_on DATE NULL.
- completion_status VARCHAR(32) NOT NULL — completed / under_construction / mixed / needs_verification.
- completion_description TEXT NOT NULL — не терять сроки по корпусам.
- completion_source_url TEXT NOT NULL; completion_checked_on DATE NOT NULL.
- notes TEXT NULL.
- created_at DATETIME(6), updated_at DATETIME(6) — UTC.
- INDEX(city, min_price_m2).

price_checked_on — дата проверки ссылки. price_observed_on — дата самой цены, если известна; неизвестную дату не подменять датой проверки. Структурированные даты ввода не выдумывать из текстового диапазона.

## apartment_lots — квартиры в ЖК

- id BIGINT UNSIGNED PK.
- complex_id BIGINT UNSIGNED NOT NULL FK → residential_complexes.id, ON DELETE RESTRICT.
- external_id VARCHAR(150) NOT NULL — стабильный ID квартиры в источнике.
- rooms SMALLINT UNSIGNED NOT NULL, CHECK 0..20; 0 = студия.
- area_m2 DECIMAL(8,2) NOT NULL, CHECK > 0.
- starting_price_rub DECIMAL(16,2) NOT NULL, CHECK > 0 — полная стартовая цена квартиры, не ₽/м².
- updated_at DATETIME(6) NOT NULL — дата обновления предложения источником в UTC.
- source_url TEXT NULL; building VARCHAR(100) NULL.
- is_active BOOLEAN NOT NULL DEFAULT TRUE.
- is_demo BOOLEAN NOT NULL DEFAULT FALSE.
- imported_at DATETIME(6) NOT NULL — фактическое время загрузки.
- UNIQUE(complex_id, external_id).
- INDEX(complex_id, is_active, is_demo, area_m2, starting_price_rub).

Десятичные значения обрабатывать Decimal, не float. Точность денег — копейки. Даты источника без времени трактовать как 00:00:00 UTC и сохранить это правило в руководстве импорта. Будущая дата обновления — ошибка импорта.

## Управление

backend CLI: complexes-import <file>, lots-import <file>, lot-deactivate <complex-slug> <external-id>. Все проходят общую валидацию и транзакции; импорт по стабильным ключам идемпотентен. Весь файл проверяется до записи; ошибка любой строки откатывает весь файл и выдаёт номер строки. Удаление отсутствующих в файле лотов автоматически не выполняется; снятие — явное is_active=false.

API только читает. Автообновление из сайтов и CRUD HTTP endpoints вне MVP. OpenAPI JSON, Swagger, ReDoc и отдельный HTTP healthcheck отключены: единственный прикладной маршрут — поиск. Проверка готовности контейнеров выполняется командами/подключением к БД.
