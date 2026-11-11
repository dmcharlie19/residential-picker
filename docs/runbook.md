# Локальный запуск и обслуживание

Нужны Docker Desktop с Linux containers и Docker Compose v2. Команды выполняются из корня проекта в PowerShell. Порты доступны только на 127.0.0.1. Это локальная конфигурация, а не публичный production deployment.

## Первый запуск

```powershell
./scripts/init-env.ps1
docker compose config --quiet
docker compose up -d --build
```

Скрипт создаёт `.env` с двумя случайными паролями, если файла ещё нет. Альтернатива: скопировать `.env.example` в `.env` и заменить оба значения. Пароли должны состоять из URL-safe символов; при ручном использовании других символов пароль в DATABASE_URL требует URL encoding. Не коммитить `.env`, не публиковать вывод `docker compose config` без `--quiet`.

Форма: http://localhost:8080. MySQL: localhost:13306, база `residential_picker`, пользователь `residential_app`. Backend: localhost:8000. Backend дожидается успешного SELECT к MySQL, применяет миграции и запускает Uvicorn. Готовность приложения проверяется поисковым запросом, отдельного HTTP health endpoint нет:

```powershell
docker compose ps
docker compose logs --tail 50 backend
curl.exe --fail 'http://localhost:8080/api/v1/search?city=%D0%A1%D0%BE%D1%87%D0%B8&budget=20000000&area=50'
```

Точные допустимые параметры города описаны в контракте API. Пустой список после импорта исходного снимка допустим: в нём нет реальных квартир, большинство цен не имеют даты источника.

## Импорт и снятие квартиры

Каталог `data` подключён в backend как `/data` только для чтения. Сначала положить проверенный UTF-8 JSON в этот каталог, затем:

```powershell
docker compose exec backend python -m app.cli complexes-import /data/complexes.snapshot.json
docker compose exec backend python -m app.cli lots-import /data/lots.example.json
docker compose exec backend python -m app.cli lot-deactivate complex-slug external-id
```

`lots.example.json` — пример формата; импортировать только после проверки содержимого и источников. Повтор снимка идемпотентен, но не должен затирать более свежие данные. Для явного удаления известной цены предусмотрен `--allow-clear-price`; конфликты требуют решения оператора. Даты источника без времени трактуются как 00:00 UTC. Импортное время не освежает предложение. Ошибка строки откатывает весь файл; ненулевой exit code означает неуспех. Снятие отсутствующих в файле лотов автоматически не выполняется.

## Отдельная демонстрация

```powershell
./scripts/run-demo.ps1
```

Скрипт запускает только три demo-сервиса, ждёт миграций и вызывает `demo-seed`. Форма: http://localhost:8081, API: localhost:8001, MySQL: localhost:13307. Отдельные база `residential_picker_demo`, пользователь `demo_app`, контейнер и volume защищают реальный каталог от смешивания. Фиксированные пароли demo предназначены только для локального показа. При повторном запуске seed обновляет демонстрационные даты относительно текущего времени.

Ручной эквивалент:

```powershell
docker compose --profile demo up -d --build demo-frontend
docker compose --profile demo exec demo-backend python -m app.cli demo-seed
```

Сразу после `up -d` backend ещё может применять миграции: при ручном запуске дождаться сообщения Uvicorn о старте перед seed.

## Остановка и сохранность

```powershell
docker compose stop
docker compose --profile demo stop demo-frontend demo-backend demo-mysql
```

Данные сохраняются в `residential-picker-mysql-data` и `residential-picker-demo-mysql-data`. Не применять `docker compose down -v`: это удаляет базы. Изменение паролей в `.env` не меняет учётные данные существующего MySQL volume. При ротации сначала менять пароль пользователя в БД, затем конфигурацию и пересоздавать backend.

## Резервная копия и восстановление

Копия содержит реальные данные, хранить её вне git с ограниченным доступом. Следующие команды используют пароль из окружения контейнера и не выводят его. Копирование через `docker cp` сохраняет байты дампа и кириллицу независимо от версии PowerShell.

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump -u "$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF --databases "$MYSQL_DATABASE" > /tmp/residential-picker-backup.sql'
$dbContainer = docker compose ps -q mysql
docker cp "${dbContainer}:/tmp/residential-picker-backup.sql" ./backups/residential-picker.sql
docker compose exec -T mysql rm /tmp/residential-picker-backup.sql
```

Восстановление заменяет данные целевой базы; выполнять только после проверки файла и новой резервной копии. На время восстановления остановить запись/импорт и backend:

```powershell
docker compose stop backend frontend
$dbContainer = docker compose ps -q mysql
docker cp ./backups/residential-picker.sql "${dbContainer}:/tmp/restore.sql"
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" < /tmp/restore.sql'
docker compose exec -T mysql rm /tmp/restore.sql
docker compose up -d backend frontend
```

Проверять exit code каждой команды. Перед восстановлением новой версии приложения проверить совместимость её миграций с дампом.

## Явный сброс только demo

Эти команды удаляют исключительно демонстрационные данные. Реальные сервисы и volume не затрагиваются.

```powershell
docker compose --profile demo stop demo-frontend demo-backend demo-mysql
docker compose --profile demo rm -f demo-frontend demo-backend demo-mysql
docker volume rm residential-picker-demo-mysql-data
./scripts/run-demo.ps1
```
