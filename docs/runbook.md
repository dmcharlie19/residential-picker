# Запуск и обслуживание SQLite

## Docker

Из корня проекта: docker compose up -d --build. Backend применяет миграции Alembic перед запуском Uvicorn. Интерфейс: http://localhost:8080. API: http://localhost:8000. Сервисы слушают только 127.0.0.1.

Compose содержит только backend/frontend. Файл data/residential-picker.sqlite3 подключён через каталог /app/storage. Каталог data также доступен в backend только для чтения как /data для JSON-импорта. .env с паролями не используется; старый файл .env можно оставить, он не влияет на SQLite-конфигурацию Compose.

## Импорт

```powershell
docker compose exec -T backend python -m app.cli complexes-import /data/complexes.snapshot.json
docker compose exec -T backend python -m app.cli lots-import /data/lots.example.json
docker compose exec -T backend python -m app.cli lot-deactivate complex-slug external-id
```

JSON-файлы помещаются в data. Реальных квартир в примере нет. Ошибка откатывает файл целиком; ключи стабильны, повторный импорт идемпотентен. Более старая цена не перезаписывает свежую. Для удаления известной цены нужен явный --allow-clear-price.

## Файл и точность

SQLite встроена в Python. Подключения включают foreign_keys=ON, WAL и busy_timeout=15000. Путь DATABASE_URL должен вести к файлу; in-memory базы не допускаются. В таблицах min_price_m2 и starting_price_rub — INTEGER в копейках, area_m2 — INTEGER в сотых м². ORM переводит их в Decimal; SQL-функция estimate_cents рассчитывает стоимость без float. Даты-время хранятся как UTC без timezone.

## Резервная копия

Не копировать только основной файл при активном WAL. Использовать SQLite backup API (копия сохраняется рядом с базой):

```powershell
docker compose exec -T backend python -c 'import sqlite3; src=sqlite3.connect("/app/storage/residential-picker.sqlite3"); dst=sqlite3.connect("/app/storage/catalog-backup.sqlite3"); src.backup(dst); dst.close(); src.close()'
```

Для восстановления сначала остановить backend: docker compose stop backend. Сохранить текущую базу вместе с -wal/-shm, если они существуют. Восстанавливать в новый файл из проверенной копии, не оставляя старые -wal/-shm под тем же именем; затем указать восстановленный путь DATABASE_URL или заменить исходный файл после сохранения старого комплекта. Запустить docker compose up -d backend. Миграции выполнятся автоматически. Перед восстановлением проверить совместимость версии схемы.

## Переход с прежней базы

Перед переносом сохранён backups/before-sqlite.json. В пустой SQLite применены миграции и перенесены все 15 ЖК, включая ID, источники, цены и даты. Старые Docker volumes не удаляются автоматически. Утилита scripts/restore-catalog.py отказывается писать в непустую SQLite-базу. Для её ручного использования задать PYTHONPATH=backend и выполнить Python из виртуального окружения.

## Тесты

scripts/test-backend.ps1 устанавливает зафиксированные зависимости и запускает pytest. Docker и отдельная СУБД для этих тестов не нужны. Каждый запуск создаёт временный файл SQLite; рабочая база не очищается. Временные файлы управляются pytest.
