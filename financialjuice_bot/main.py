#!/usr/bin/env python3
"""
FinancialJuice -> Telegram alert bot.

Uses the public FinancialJuice RSS feed. No ChatGPT/OpenAI API is required.
Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as environment variables.

The bot:
- polls the RSS feed
- deduplicates items in SQLite
- alerts on high-impact / market-moving headlines
- keeps a configurable lookback window
- is suitable for GitHub Actions
"""

import html
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RSS_URL = os.getenv(
    "FINANCIALJUICE_RSS_URL",
    "https://www.financialjuice.com/feed.ashx?xy=rss",
)
DB_PATH = os.getenv("STATE_DB", "financialjuice_state.sqlite3")
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "180"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "50"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# High-impact and market-moving terms. Tune this list for your trading style.
HIGH_IMPACT = re.compile(
    r"\b("
    r"red|high impact|high-impact|market moving|market-moving|"
    r"fomc|fed|powell|nfp|non[- ]farm|payroll|cpi|pce|gdp|ppi|"
    r"ism|pmi|retail sales|jobless|unemployment|interest rate|rate decision|"
    r"tariff|trump|treasury|bond yields?|dxy|gold|xau|oil|crude|opec|"
    r"ecb|lagarde|boe|bo[ej]|boj|snb|rba|rbnz|bank of canada|"
    r"war|ceasefire|sanctions|missile|invasion|"
    r"usd|eur|gbp|jpy|cad|aud|nzd|chf"
    r")\b",
    re.IGNORECASE,
)

RED_MARKERS = re.compile(
    r"\b(red|high impact|high-impact|market moving|market-moving)\b",
    re.IGNORECASE,
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sent (item_id TEXT PRIMARY KEY, sent_at INTEGER NOT NULL)"
    )
    conn.commit()
    return conn


def fetch_rss():
    req = urllib.request.Request(
        RSS_URL,
        headers={
            "User-Agent": "PoladliFX-FinancialJuice-Bot/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
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
        ts = parse_date(pub) or int(time.time())
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


def is_relevant(item):
    text = f"{item['title']} {item['description']}"
    return bool(HIGH_IMPACT.search(text))


def was_sent(conn, item_id):
    return conn.execute("SELECT 1 FROM sent WHERE item_id=?", (item_id,)).fetchone() is not None


def mark_sent(conn, item_id):
    conn.execute(
        "INSERT OR IGNORE INTO sent(item_id, sent_at) VALUES (?, ?)",
        (item_id, int(time.time())),
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


def format_message(item):
    dt = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc)
    label = "🔴 HIGH IMPACT" if RED_MARKERS.search(
        f"{item['title']} {item['description']}"
    ) else "🟠 MARKET MOVING"

    title = html.escape(item["title"] or "FinancialJuice alert")
    desc = html.escape(item["description"][:700])
    link = html.escape(item["link"], quote=True)

    parts = [
        f"<b>{label}</b>",
        f"<b>{title}</b>",
        f"🕒 {dt.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    if desc:
        parts.append(desc)
    if link:
        parts.append(f'🔗 <a href="{link}">FinancialJuice</a>')
    return "\n".join(parts)


def cleanup(conn):
    cutoff = int(time.time()) - 7 * 86400
    conn.execute("DELETE FROM sent WHERE sent_at < ?", (cutoff,))
    conn.commit()


def main():
    conn = db()
    cleanup(conn)

    raw = fetch_rss()
    items = parse_items(raw)
    now = int(time.time())
    cutoff = now - LOOKBACK_MINUTES * 60

    # Process oldest first so multiple new alerts arrive in chronological order.
    candidates = [
        x for x in items
        if x["timestamp"] >= cutoff and is_relevant(x) and not was_sent(conn, x["id"])
    ]
    candidates.sort(key=lambda x: x["timestamp"])

    print(f"Fetched {len(items)} RSS items; {len(candidates)} new relevant alerts.")

    for item in candidates:
        message = format_message(item)
        telegram_send(message)
        mark_sent(conn, item["id"])

    conn.close()


if __name__ == "__main__":
    main()
