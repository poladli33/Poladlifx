import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Tuple

from .config import POLL_MINUTES, TIMEZONE
from .filters import actual_vs_forecast, news_impact
from .models import CalendarEvent, NewsItem


def local_time(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, timezone.utc).astimezone(ZoneInfo(TIMEZONE))
    return dt.strftime("%Y-%m-%d %H:%M %Z")


def _markets_text(markets: Tuple[str, ...]) -> str:
    return " / ".join(markets)


def format_news(item: NewsItem) -> str:
    impact = news_impact(f"{item.title} {item.description}")
    title = html.escape(item.title or "FinancialJuice alert")
    desc = html.escape(item.description[:800])
    link = html.escape(item.link, quote=True)
    parts = [
        "<b>📰 FINANCIALJUICE</b>",
        f"<b>Impact: {impact}</b>",
        f"<b>{title}</b>",
        f"🕒 {local_time(item.timestamp_utc)}",
    ]
    if desc:
        parts.append(desc)
    if link:
        parts.append(f'🔗 <a href="{link}">FinancialJuice</a>')
    return "\n".join(parts)


def format_pre_event(event: CalendarEvent, minutes: int) -> str:
    return "\n".join(
        [
            "<b>📅 ECONOMIC CALENDAR</b>",
            f"<b>⏰ T−{minutes} MIN</b>",
            f"{html.escape(event.currency)} → <b>{html.escape(_markets_text(event.markets))}</b>",
            f"<b>{html.escape(event.event_name)}</b>",
            f"Impact: <b>{html.escape(event.impact)}</b>",
            f"🕒 {local_time(event.timestamp_utc)}",
            f"Forecast: {html.escape(event.forecast or '—')}",
            f"Previous: {html.escape(event.previous or '—')}",
        ]
    )


def format_actual(event: CalendarEvent) -> str:
    verdict = actual_vs_forecast(event.event_name, event.actual, event.forecast)
    parts = [
        "<b>📊 ECONOMIC CALENDAR — ACTUAL</b>",
        f"{html.escape(event.currency)} → <b>{html.escape(_markets_text(event.markets))}</b>",
        f"<b>{html.escape(event.event_name)}</b>",
        f"Impact: <b>{html.escape(event.impact)}</b>",
        f"Actual: <b>{html.escape(event.actual or '—')}</b>",
        f"Forecast: {html.escape(event.forecast or '—')}",
        f"Previous: {html.escape(event.previous or '—')}",
        f"Result: <b>{html.escape(verdict.label)}</b>",
    ]
    if event.revised_previous:
        parts.append(f"Revised Previous: {html.escape(event.revised_previous)}")
    return "\n".join(parts)


def pre_alert_key(event_id: str, minutes: int) -> str:
    return f"calendar:{event_id}:pre:{minutes}"


def should_fire_pre_alert(event: CalendarEvent, now_ts: int, minutes: int) -> bool:
    delta = event.timestamp_utc - now_ts
    target = minutes * 60
    lower = max(0, target - POLL_MINUTES * 60 - 20)
    upper = target + 20
    return lower <= delta <= upper
