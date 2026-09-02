# PoladliFX — FinancialJuice → Telegram Economic Alerts

This project is an autonomous Telegram alert bot designed for GitHub Actions.

## What is implemented

- FinancialJuice **public RSS** is used for headlines only. No closed endpoint scraping, anti-bot bypass, or hidden API extraction is used.
- Economic-calendar data is obtained through a separate calendar-provider adapter. The included adapter targets **Trading Economics REST API** and expects a licensed `TRADING_ECONOMICS_API_KEY`.
- Events are normalized into: `event_id`, `timestamp_utc`, `country`, `currency`, `event_name`, `impact`, `actual`, `forecast`, `previous`, `revised_previous`, `source`, and status/state fields.
- Impact is normalized as `EXTREME`, `HIGH`, `MEDIUM`, `LOW`. Provider importance (1/2/3) is respected, but critical event names such as FOMC/CPI/PCE/NFP/Powell can be promoted to `EXTREME`.
- Currency-to-instrument mapping covers `XAUUSD`, `DXY`, `EURUSD`, `GBPUSD`, `USDJPY`, and `USDCAD`.
- Calendar notifications support T−30, T−15, T−5 and T+0/Actual, with per-event deduplication.
- Actual vs Forecast classification supports direction-aware labels such as `MUCH BETTER`, `IN LINE`, and `MUCH WORSE`; metrics without a meaningful universal direction use `ABOVE FORECAST` / `BELOW FORECAST` instead of pretending that the result is intrinsically better or worse.
- Persistent state is stored in `data/state.json` and committed back to the repository only when it changes. GitHub Actions therefore does not depend on the runner filesystem surviving between jobs.
- Unit tests use only the Python standard library.

## Important provider note

FinancialJuice Terms prohibit automated collection, aggregation, copying, or extraction of the Service/content unless expressly permitted in writing. This project therefore keeps FinancialJuice usage to its public RSS feed and does not attempt to reverse-engineer closed endpoints.

For the calendar, do not assume that an old `guest:guest` Trading Economics example is a production/free entitlement. The current Trading Economics documentation requires an API key/plan for REST access. Configure `TRADING_ECONOMICS_API_KEY` as a GitHub Actions secret.

## GitHub setup

Repository **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TRADING_ECONOMICS_API_KEY`

The workflow requests `contents: write` because it persists `data/state.json` back to the repository. GitHub's checkout action keeps credentials available for authenticated `git push` in later workflow steps.

## Run

The workflow is scheduled for `*/5 * * * *`. GitHub schedules are best-effort and can be delayed, so pre-event windows are intentionally tolerant of a few minutes of drift.

Manual run: **Actions → PoladliFX FinancialJuice Alerts → Run workflow**.

## Structure

```text
financialjuice_bot/
├── alerts.py
├── calendar.py
├── config.py
├── filters.py
├── instruments.py
├── main.py
├── models.py
├── news.py
├── storage.py
└── telegram.py

data/state.json
tests/
.github/workflows/financialjuice.yml
.env.example
requirements.txt
README.md
```

## Local dry run

```bash
export DRY_RUN=true
export TELEGRAM_BOT_TOKEN=dummy
export TELEGRAM_CHAT_ID=dummy
python -m unittest discover -s tests -v
python -m financialjuice_bot.main
```

Calendar requests still require a valid calendar API key when `ENABLE_CALENDAR=true`.
