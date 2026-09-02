# PoladliFX — FinancialJuice RED Realtime Telegram Bot

Бот разделяет **Economic Calendar** и **Headlines/News**.

## 1. Экономический календарь — отдельно

Источник: живая страница FinancialJuice `/home`.

Фильтр:

- только **красные / RED / HIGH IMPACT** строки;
- оранжевые строки не отправляются;
- для календаря используются строки с `Actual / Forecast / Previous`, как в вашем скриншоте.

Логика:

- каждые **5 секунд** бот перечитывает уже открытую страницу FinancialJuice;
- перед событием — **T-5 минут**;
- когда время события наступило и строка стала опубликованной, бот отправляет его **сразу** при следующей проверке;
- время Telegram форматируется как **Baku / Asia-Baku (UTC+4)**;
- в **09:00 Baku** отправляется отдельный список всех красных событий на сегодня.

## 2. FinancialJuice Headlines / News — отдельно

RSS FinancialJuice остается отдельным резервным каналом для **явно помеченных RED/HIGH IMPACT headlines**. Обычные слова `USD`, `Fed`, `gold` сами по себе не считаются красным impact.

RSS проверяется не каждые 5 секунд, а примерно раз в 15 секунд, чтобы не создавать лишнюю нагрузку. Календарь при этом проверяется каждые 5 секунд.

## 3. Почему 5 секунд, а не GitHub Actions cron

GitHub Actions cron не является realtime-планировщиком и может запускаться с задержкой. Поэтому для настоящего режима `5 sec polling` бот сделан как **постоянно работающий процесс**.

В архиве есть Docker-конфигурация для VPS/сервера:

```bash
cp .env.example .env
# заполнить TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
mkdir -p data
docker compose up -d --build
```

Контейнер настроен на `restart: unless-stopped`, поэтому после перезапуска сервера бот поднимется автоматически.

## 4. GitHub Actions

`.github/workflows/financialjuice.yml` оставлен для ручного запуска тестового realtime-сеанса. Это не замена постоянному VPS/контейнеру.

`.github/workflows/financialjuice-once.yml` — одноразовая проверка.

## 5. Secrets

Для GitHub Actions добавьте:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## 6. Локальный запуск

```bash
pip install -r requirements.txt
python -m playwright install chromium
RUN_MODE=realtime python financialjuice_bot/main.py
```

Для одноразовой проверки:

```bash
RUN_MODE=once DRY_RUN=true python financialjuice_bot/main.py
```

## Важный момент по realtime

Бот обнаруживает изменение с интервалом по умолчанию **5 секунд**. Реальная задержка зависит от того, когда само событие появляется/обновляется на FinancialJuice и когда браузерный DOM получает это обновление. Поэтому это не гарантирует математически нулевую задержку, но убирает прежнюю модель `GitHub cron раз в 5 минут`.
