#!/usr/bin/env python3
"""
PoladliFX FinancialJuice -> Telegram.

Important:
- All displayed/scheduled times are converted to Asia/Baku (UTC+4).
- Breaking alerts are limited to fresh RSS items, so an old headline is never
  sent hours later just because the GitHub runner started late.
- Only explicit FinancialJuice high-impact / market-moving markers are sent
  (red/orange). Generic words such as "Fed", "gold", "USD" are NOT enough.
- At 09:00 Baku, a digest of today's red/orange headlines is sent.
- The RSS feed itself does not provide a reliable future economic-calendar
  event time. Therefore a true "5 minutes before release" alert cannot be
  guaranteed from RSS alone. The code includes an optional calendar JSON feed
  hook (CALENDAR_JSON_URL) for a source that exposes event_time + impact.
"""

import html
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

RSS_URL = os.getenv(
    "FINANCIALJUICE_RSS_URL",
    "https://www.financialjuice.com/feed.ashx?xy=rss",
)
DB_PATH = os.getenv("STATE_DB", "financialjuice_state.sqlite3")
BAKU = ZoneInfo("Asia/Baku")

# RSS freshness window. Keep this short so an old news item is not delivered
# hours later. 12 minutes gives some tolerance for GitHub Actions scheduling.
FRESH_MINUTES = int(os.getenv("FRESH_MINUTES", "12"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "100"))

# Daily digest time in Baku.
DAILY_DIGEST_HOUR = int(os.getenv("DAILY_DIGEST_HOUR", "9"))
DAILY_DIGEST_MINUTE = int(os.getenv("DAILY_DIGEST_MINUTE", "0"))
RUN_DAILY_DIGEST = os.getenv("RUN_DAILY_DIGEST", "false").lower() == "true"

# Optional calendar feed for real 5-minute pre-event alerts.
CALENDAR_JSON_URL = os.getenv("CALENDAR_JSON_URL", "").strip()
PRE_ALERT_MINUTES = int(os.getenv("PRE_ALERT_MINUTES", "5"))

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# FinancialJuice's RSS/search result does not expose the UI color as a stable
# XML field. We therefore only accept explicit impact labels.
RED_MARKERS = re.compile(
    r"\b(?:red|high\s*impact|high-impact)\b", re.IGNORECASE
)
ORANGE_MARKERS = re.compile(
    r"\b(?:orange|market\s*moving|market-moving|medium\s*impact|medium-impact)\b",
    re.IGNORECASE,
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sent (
            item_id TEXT PRIMARY KEY,
            sent_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def fetch_url(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PoladliFX-FinancialJuice-Bot/2.0",
            "Accept": "application/rss+xml, application/json, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def strip_html(value):
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value or "")
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def parse_date(value):
    if not value:
        return None
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def parse_items(raw):
    root = ET.fromstring(raw)
    items = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        description = strip_html(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        pub = (item.findtext("pubDate") or "").strip()

        ts = parse_date(pub)
        # Never invent "now" for a missing publication date. Doing that can
        # turn a very old RSS item into a fresh alert.
        if ts is None:
            continue

        items.append(
            {
                "id": guid,
                "title": title,
                "description": description,
                "link": link,
                "timestamp": ts,
            }
        )

    return items[:MAX_ITEMS]


def impact(item):
    text = f"{item['title']} {item['description']}"
    if RED_MARKERS.search(text):
        return "red"
    if ORANGE_MARKERS.search(text):
        return "orange"
    return None


def is_red_or_orange(item):
    return impact(item) in {"red", "orange"}


def was_sent(conn, item_id):
    return (
        conn.execute("SELECT 1 FROM sent WHERE item_id=?", (item_id,)).fetchone()
        is not None
    )


def mark_sent(conn, item_id):
    conn.execute(
        "INSERT OR IGNORE INTO sent(item_id, sent_at) VALUES (?, ?)",
        (item_id, int(time.time())),
    )
    conn.commit()


def was_digest_sent(conn, local_date):
    row = conn.execute(
        "SELECT value FROM meta WHERE key='digest_date'"
    ).fetchone()
    return row and row[0] == local_date.isoformat()


def mark_digest_sent(conn, local_date):
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('digest_date', ?)",
        (local_date.isoformat(),),
    )
    conn.commit()


def telegram_send(message):
    if DRY_RUN:
        print(message)
        return

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram HTTP {response.status}")


def format_message(item, prefix=""):
    local_dt = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc).astimezone(BAKU)
    level = impact(item)
    label = "🔴 RED / HIGH IMPACT" if level == "red" else "🟠 ORANGE / MARKET MOVING"

    title = html.escape(item["title"] or "FinancialJuice alert")
    desc = html.escape(item["description"][:700])
    link = html.escape(item["link"], quote=True)

    parts = [
        f"<b>{prefix}{label}</b>",
        f"<b>{title}</b>",
        f"🕒 {local_dt.strftime('%d.%m.%Y %H:%M')} Baku",
    ]
    if desc:
        parts.append(desc)
    if link:
        parts.append(f'🔗 <a href="{link}">FinancialJuice</a>')
    return "\n".join(parts)


def format_digest(items, local_date):
    header = (
        f"🗓 <b>Сегодняшние RED + ORANGE новости</b>\n"
        f"📍 Baku • {local_date.strftime('%d.%m.%Y')}\n"
        f"Всего: <b>{len(items)}</b>"
    )
    if not items:
        return header + "\n\nНет красных/оранжевых новостей на данный момент."

    lines = [header, ""]
    for item in sorted(items, key=lambda x: x["timestamp"]):
        local_dt = datetime.fromtimestamp(
            item["timestamp"], tz=timezone.utc
        ).astimezone(BAKU)
        level = impact(item)
        icon = "🔴" if level == "red" else "🟠"
        title = html.escape(item["title"] or "Без заголовка")
        lines.append(
            f"{icon} <b>{local_dt.strftime('%H:%M')}</b> — {title}"
        )
        if item["link"]:
            lines.append(
                f'   <a href="{html.escape(item["link"], quote=True)}">Открыть</a>'
            )
    return "\n".join(lines)


def cleanup(conn):
    cutoff = int(time.time()) - 14 * 86400
    conn.execute("DELETE FROM sent WHERE sent_at < ?", (cutoff,))
    conn.commit()


def run_breaking_alerts(conn, items, now_ts):
    cutoff = now_ts - FRESH_MINUTES * 60

    candidates = [
        x for x in items
        if cutoff <= x["timestamp"] <= now_ts + 60
        and is_red_or_orange(x)
        and not was_sent(conn, x["id"])
    ]
    candidates.sort(key=lambda x: x["timestamp"])

    print(
        f"Fresh window: {FRESH_MINUTES}m; "
        f"found {len(candidates)} new red/orange alerts."
    )

    for item in candidates:
        telegram_send(format_message(item))
        mark_sent(conn, item["id"])


def run_daily_digest(conn, items, now_local):
    # GitHub has a separate 09:00 Baku cron. This extra guard prevents a
    # manual/retried run from sending the digest twice on the same day.
    if not RUN_DAILY_DIGEST:
        return

    if was_digest_sent(conn, now_local.date()):
        print("Today's digest already sent.")
        return

    start = datetime.combine(now_local.date(), datetime.min.time(), tzinfo=BAKU)
    end = now_local
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    today = [
        x for x in items
        if start_ts <= x["timestamp"] <= end_ts
        and is_red_or_orange(x)
    ]
    today.sort(key=lambda x: x["timestamp"])

    telegram_send(format_digest(today, now_local.date()))
    mark_digest_sent(conn, now_local.date())


def parse_calendar_json(raw):
    """
    Optional generic calendar format:

    [
      {
        "id": "nfp-2026-09-04",
        "title": "US Nonfarm Payrolls",
        "event_time": "2026-09-04T12:30:00Z",
        "impact": "red"
      }
    ]

    event_time may also contain a Baku offset. Only red/orange events are used.
    """
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict):
        data = data.get("events", data.get("data", []))

    result = []
    for event in data:
        level = str(event.get("impact", "")).lower()
        if level not in {"red", "orange"}:
            continue

        raw_time = event.get("event_time") or event.get("time")
        if not raw_time:
            continue

        try:
            dt = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BAKU)
            ts = int(dt.timestamp())
        except Exception:
            continue

        result.append(
            {
                "id": str(event.get("id") or f"{event.get('title')}:{ts}"),
                "title": str(event.get("title") or "Economic event"),
                "timestamp": ts,
                "impact": level,
            }
        )
    return result


def run_pre_alerts(conn, now_ts):
    if not CALENDAR_JSON_URL:
        return

    raw = fetch_url(CALENDAR_JSON_URL)
    events = parse_calendar_json(raw)

    # Alert in a narrow +/- 45 second window around T-5 minutes. Since the
    # workflow runs every 5 minutes, this avoids sending the same pre-alert
    # multiple times.
    target = now_ts + PRE_ALERT_MINUTES * 60
    window = 45

    for event in events:
        if abs(event["timestamp"] - target) > window:
            continue

        key = f"pre:{event['id']}:{PRE_ALERT_MINUTES}"
        if was_sent(conn, key):
            continue

        local_dt = datetime.fromtimestamp(
            event["timestamp"], tz=timezone.utc
        ).astimezone(BAKU)
        icon = "🔴" if event["impact"] == "red" else "🟠"

        message = (
            f"<b>⏰ {icon} NEWS IN {PRE_ALERT_MINUTES} MINUTES</b>\n"
            f"<b>{html.escape(event['title'])}</b>\n"
            f"🕒 {local_dt.strftime('%d.%m.%Y %H:%M')} Baku"
        )
        telegram_send(message)
        mark_sent(conn, key)


def main():
    conn = db()
    cleanup(conn)

    now_ts = int(time.time())
    now_local = datetime.fromtimestamp(now_ts, tz=timezone.utc).astimezone(BAKU)

    raw = fetch_url(RSS_URL)
    items = parse_items(raw)

    print(
        f"Fetched {len(items)} RSS items at "
        f"{now_local.strftime('%Y-%m-%d %H:%M:%S')} Baku."
    )

    run_breaking_alerts(conn, items, now_ts)
    run_daily_digest(conn, items, now_local)
    run_pre_alerts(conn, now_ts)

    conn.close()


if __name__ == "__main__":
    main()
