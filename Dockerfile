FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY financialjuice_bot ./financialjuice_bot

ENV RUN_MODE=realtime \
    POLL_INTERVAL_SECONDS=5 \
    PAGE_REFRESH_SECONDS=60 \
    FRESH_MINUTES=12 \
    PRE_ALERT_MINUTES=5 \
    PRE_ALERT_WINDOW_SECONDS=30 \
    HOME_WAIT_SECONDS=8 \
    DAILY_DIGEST_HOUR=9 \
    DAILY_DIGEST_MINUTE=0 \
    DAILY_DIGEST_WINDOW_SECONDS=90 \
    PYTHONUNBUFFERED=1

CMD ["python", "financialjuice_bot/main.py"]
