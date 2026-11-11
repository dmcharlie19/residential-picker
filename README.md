# КВАДРАТ — подбор квартир в ЖК

Python/FastAPI + React/TypeScript/Vite + SQLite в файле. Отдельный сервер базы данных и пароли не нужны.

## Запуск

```powershell
docker compose up -d --build
```

Открыть http://localhost:8080. Backend: http://localhost:8000.

Файл базы на компьютере: **data/residential-picker.sqlite3**. В контейнере тот же файл доступен как /app/storage/residential-picker.sqlite3 через bind mount. Пересоздание контейнера его не удаляет. Рядом могут находиться служебные файлы -wal и -shm.

В текущий файл перенесены 15 ЖК из прежнего каталога. Реальных квартир в исходных данных нет, поэтому пустая выдача до импорта лотов или свежих датированных цен ожидаема.

Для новой пустой базы после запуска backend:

```powershell
docker compose exec -T backend python -m app.cli complexes-import /data/complexes.snapshot.json
```

## Без Docker

Нужен Python >=3.13. Из корня проекта:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
cd backend
../.venv/Scripts/python.exe -m alembic upgrade head
../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

По умолчанию используется тот же файл data/residential-picker.sqlite3. Из другого терминала: cd frontend; npm ci; npm run dev. Для frontend нужен Node >=20.19. При необходимости путь меняется переменной DATABASE_URL (SQLite URL с абсолютным путём).

## Подбор и данные

- Один endpoint: GET /api/v1/search?city=Сочи&budget=20000000&area=50.
- До трёх разных ЖК; площадь от желаемой до +10%; бюджет — жёсткий максимум.
- Актуальность 30 суток; снятые и устаревшие лоты исключаются.
- Расчёт по м² допустим только при отсутствии реальных записей лотов и наличии свежей датированной цены.
- Две основные таблицы: residential_complexes и apartment_lots.
- Деньги хранятся целыми копейками, площадь — сотыми долями м²; API по-прежнему возвращает десятичные строки.
- Импорт и обновление через backend CLI. В Compose только backend и frontend, без demo-сервисов.

## Проверки

```powershell
./scripts/test-backend.ps1
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend-тесты работают с отдельным временным SQLite-файлом, не затрагивая каталог. Браузерной проверке нужен запущенный основной интерфейс; BASE_URL и BROWSER_EXECUTABLE_PATH позволяют изменить адрес и Chromium.

[Архитектура](docs/architecture.md) · [API](docs/api.md) · [Алгоритм](docs/search.md) · [Обслуживание](docs/runbook.md) · [Проверки](docs/verification.md) · [План](PLAN.md)
