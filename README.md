# PoladliFX — FinancialJuice → Telegram Alerts

Autonomous GitHub Actions bot for monitoring the public FinancialJuice RSS feed and sending selected high-impact / market-moving headlines to Telegram.

## What it does

- Polls the public FinancialJuice RSS feed.
- Filters for high-impact and market-moving terms.
- Deduplicates alerts using SQLite.
- Sends HTML-formatted Telegram messages.
- Runs from GitHub Actions, so ChatGPT is **not required at runtime**.

The feed endpoint used by this project is the publicly referenced FinancialJuice RSS endpoint:
`https://www.financialjuice.com/feed.ashx?xy=rss`

## GitHub Secrets

In the repository:

**Settings → Secrets and variables → Actions**

Create:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Do not commit either credential to the repository.

## Telegram setup

1. Open Telegram and talk to `@BotFather`.
2. Create a bot with `/newbot`.
3. Copy the bot token into `TELEGRAM_BOT_TOKEN`.
4. Add the bot to the target chat/channel and give it permission to post.
5. Put the target chat ID into `TELEGRAM_CHAT_ID`.

## Run

Open:

**Actions → FinancialJuice Telegram Alerts → Run workflow**

The scheduled workflow is configured to poll approximately every 5 minutes. GitHub Actions schedules are best-effort and can be delayed.

## Filtering

The keyword filter is intentionally broad. Edit `HIGH_IMPACT` in `financialjuice_bot/main.py` to make alerts stricter for your ICT/XAUUSD workflow.

Suggested next improvements:

- separate XAUUSD / DXY / USD / indices filters
- economic-calendar pre-event alerts
- 30/15/5 minute reminders
- actual/forecast/previous comparison
- duplicate headline clustering
- Telegram topics
- severity levels A/B/C
- quiet hours
