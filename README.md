# PoladliFX — FinancialJuice RED alerts -> Telegram

## Что изменено

Теперь основной источник — **живая страница FinancialJuice `/home`**, а не только RSS.
Бот запускает headless Chromium и читает DOM после загрузки страницы. Это важно, потому что экономический календарь на `/home` отображается динамически.

### Фильтр — только RED

Берутся только строки календаря, которые FinancialJuice реально отрисовал красным цветом и которые содержат `Actual / Forecast / Previous`, как в вашем скриншоте.

Пример из скриншота:

`New Zealand Cash Rate Actual 2.75% (Forecast 2.75%, Previous 2.50%)`

Оранжевые строки полностью игнорируются.

### Время — Baku

Chromium запускается с timezone `Asia/Baku`, а Telegram-сообщения дополнительно форматируются в Baku (`UTC+4`). Поэтому время календаря не должно смещаться на несколько часов из-за UTC/локального времени runner.

### Что приходит в Telegram

1. **Красное событие после выхода** — только если оно свежее (`FRESH_MINUTES=12`). Старые события не будут приходить спустя часы.
2. **За ~5 минут до красного события** — `PRE_ALERT_MINUTES=5`. Окно `±150` секунд нужно из-за неточного времени запуска GitHub Actions.
3. **09:00 Baku** — отдельный список всех красных событий на текущий день, включая будущие и уже прошедшие на этот момент.
4. RSS оставлен только как резервный источник для сообщений, в которых FinancialJuice сам явно указывает `RED/HIGH IMPACT`. Обычные слова `Fed`, `USD`, `gold` сами по себе не проходят фильтр.

## GitHub Actions

Workflow запускается примерно каждые 5 минут.

`09:00 Baku = 05:00 UTC`, поэтому для дневного сообщения используется:

```cron
0 5 * * *
```

Github Actions может запускать scheduled workflow с задержкой. Поэтому T-5 использует окно, а отправка защищена SQLite от повторов.

## Secrets

В GitHub Repository → Settings → Secrets and variables → Actions добавьте:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Токены не должны находиться в коде.

## Локальный запуск

```bash
pip install -r requirements.txt
python -m playwright install chromium
python financialjuice_bot/main.py
```

Для теста без Telegram:

```bash
DRY_RUN=true python financialjuice_bot/main.py
```
