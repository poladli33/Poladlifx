#!/usr/bin/env python3
"""
PoladliFX — FinancialJuice -> Telegram.

The bot now reads the LIVE FinancialJuice /home page (the same calendar UI
shown in the supplied screenshot) with a headless browser.  Red calendar rows
are detected from their rendered background color, so a calendar event such as
"New Zealand Cash Rate Actual 2.75% ..." is recognized exactly like the red
row on FinancialJuice.

Rules:
- ONLY RED / HIGH-IMPACT calendar rows from FinancialJuice /home are used.
- Orange rows are intentionally ignored.
- Browser timezone is Asia/Baku, so displayed calendar times are Baku time.
- A red event is sent shortly after its release while it is still fresh.
- At 09:00 Baku a digest contains today's red events (past + upcoming).
- About 5 minutes before an upcoming red event, Telegram sends a pre-alert.
- RSS is retained only for explicit FinancialJuice RED/HIGH-IMPACT headlines;
  generic words such as USD/Fed/gold are never treated as impact markers.
"""

import hashlib
import html
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

RSS_URL = os.getenv(
    "FINANCIALJUICE_RSS_URL",
    "https://www.financialjuice.com/feed.ashx?xy=rss",
)
HOME_URL = os.getenv("FINANCIALJUICE_HOME_URL", "https://www.financialjuice.com/home")
DB_PATH = os.getenv("STATE_DB", "financialjuice_state.sqlite3")
BAKU = ZoneInfo("Asia/Baku")

FRESH_MINUTES = int(os.getenv("FRESH_MINUTES", "12"))
PRE_ALERT_MINUTES = int(os.getenv("PRE_ALERT_MINUTES", "5"))
PRE_ALERT_WINDOW_SECONDS = int(os.getenv("PRE_ALERT_WINDOW_SECONDS", "150"))
HOME_WAIT_SECONDS = int(os.getenv("HOME_WAIT_SECONDS", "8"))
MAX_HOME_EVENTS = int(os.getenv("MAX_HOME_EVENTS", "250"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "100"))

DAILY_DIGEST_HOUR = int(os.getenv("DAILY_DIGEST_HOUR", "9"))
DAILY_DIGEST_MINUTE = int(os.getenv("DAILY_DIGEST_MINUTE", "0"))
RUN_DAILY_DIGEST = os.getenv("RUN_DAILY_DIGEST", "false").lower() == "true"

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

RED_MARKERS = re.compile(r"\b(?:red|high\s*impact|high-impact)\b", re.IGNORECASE)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sent (item_id TEXT PRIMARY KEY, sent_at INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def fetch_url(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PoladliFX-FinancialJuice-Bot/3.0",
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
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def canonical_id(title, timestamp, source=""):
    raw = f"{re.sub(r'\\s+', ' ', title.lower()).strip()}|{timestamp}|{source}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def parse_rss(raw):
    root = ET.fromstring(raw)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        description = strip_html(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        ts = parse_date(pub)
        if ts is None:
            continue
        items.append(
            {
                "id": canonical_id(title, ts, "rss"),
                "title": title,
                "description": description,
                "link": link,
                "timestamp": ts,
                "source": "rss",
                "impact": "red" if RED_MARKERS.search(f"{title} {description}") else None,
            }
        )
    return items[:MAX_ITEMS]


def impact(item):
    return item.get("impact")


def was_sent(conn, item_id):
    return conn.execute(
        "SELECT 1 FROM sent WHERE item_id=?", (item_id,)
    ).fetchone() is not None


def mark_sent(conn, item_id):
    conn.execute(
        "INSERT OR IGNORE INTO sent(item_id, sent_at) VALUES (?, ?)",
        (item_id, int(time.time())),
    )
    conn.commit()


def was_digest_sent(conn, local_date):
    row = conn.execute("SELECT value FROM meta WHERE key='digest_date'").fetchone()
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
    title = html.escape(item["title"] or "FinancialJuice alert")
    desc = html.escape(item.get("description", "")[:700])
    link = html.escape(item.get("link", ""), quote=True)
    parts = [
        f"<b>{prefix}🔴 RED / HIGH IMPACT</b>",
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
        f"🗓 <b>Сегодняшние 🔴 RED / HIGH IMPACT события</b>\n"
        f"📍 Baku • {local_date.strftime('%d.%m.%Y')}\n"
        f"Всего: <b>{len(items)}</b>"
    )
    if not items:
        return header + "\n\nКрасных событий на сегодня не найдено."

    lines = [header, ""]
    for item in sorted(items, key=lambda x: x["timestamp"]):
        local_dt = datetime.fromtimestamp(item["timestamp"], timezone.utc).astimezone(BAKU)
        title = html.escape(item["title"] or "Без заголовка")
        lines.append(f"🔴 <b>{local_dt.strftime('%H:%M')}</b> — {title}")
        if item.get("link"):
            lines.append(
                f'   <a href="{html.escape(item["link"], quote=True)}">Открыть в FinancialJuice</a>'
            )
    return "\n".join(lines)


def cleanup(conn):
    cutoff = int(time.time()) - 14 * 86400
    conn.execute("DELETE FROM sent WHERE sent_at < ?", (cutoff,))
    conn.commit()


def run_breaking_alerts(conn, items, now_ts):
    cutoff = now_ts - FRESH_MINUTES * 60
    candidates = [
        x
        for x in items
        if x.get("impact") == "red"
        and cutoff <= x["timestamp"] <= now_ts + 60
        and not was_sent(conn, x["id"])
    ]
    candidates.sort(key=lambda x: x["timestamp"])
    print(f"Fresh red alerts: {len(candidates)}")

    for item in candidates:
        telegram_send(format_message(item))
        mark_sent(conn, item["id"])


def run_daily_digest(conn, items, now_local):
    if not RUN_DAILY_DIGEST:
        return
    if was_digest_sent(conn, now_local.date()):
        print("Today's digest already sent.")
        return
    today = [
        x for x in items
        if datetime.fromtimestamp(x["timestamp"], timezone.utc).astimezone(BAKU).date() == now_local.date()
        and x.get("impact") == "red"
    ]
    telegram_send(format_digest(today, now_local.date()))
    mark_digest_sent(conn, now_local.date())


def _is_red_rgb(rgb):
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rgb or "")
    if not m:
        return False
    r, g, b = map(int, m.groups())
    return r >= 120 and r > g * 1.6 and r > b * 1.6 and (r - g) >= 70


def scrape_financialjuice_home():
    """Render FinancialJuice /home in Baku timezone and detect RED rows."""
    events = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(timezone_id="Asia/Baku", locale="en-US")
        page = context.new_page()
        raw = []
        try:
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_timeout(HOME_WAIT_SECONDS * 1000)
            except PlaywrightTimeoutError:
                pass

            raw = page.evaluate(
                """
                () => {
                  const out = [];
                  const clean = s => (s || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
                  const isRed = el => {
                    const c = getComputedStyle(el);
                    const bg = c.backgroundColor || '';
                    const m = bg.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
                    if (!m) return false;
                    const [r,g,b] = m.slice(1).map(Number);
                    return r >= 120 && r > g * 1.6 && r > b * 1.6 && (r - g) >= 70;
                  };
                  for (const el of document.querySelectorAll('a, div, li, tr, article, section')) {
                    const txt = clean(el.innerText);
                    if (txt.length < 25 || txt.length > 500) continue;
                    if (!/actual/i.test(txt) || !/forecast/i.test(txt) || !/previous/i.test(txt)) continue;
                    if (!isRed(el)) continue;
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 80 || rect.height < 10) continue;
                    const lines = (el.innerText || '').split(/\\n+/).map(clean).filter(Boolean);
                    const title = lines.find(x => /actual/i.test(x) && /forecast/i.test(x) && /previous/i.test(x)) || lines[0] || txt;
                    const timeLine = lines.find(x => /\\b\\d{1,2}:\\d{2}\\s+[A-Za-z]{3}\\s+\\d{1,2}(?:\\s+\\d{4})?\\b/.test(x)) || '';
                    const linkEl = el.closest('a') || el.querySelector('a');
                    out.push({text: txt, title, timeLine, href: linkEl ? linkEl.href : ''});
                  }
                  return out;
                }
                """
            )
        finally:
            context.close()
            browser.close()

    # De-duplicate DOM ancestors that represent the same row.
    unique = {}
    for item in raw:
        title = re.sub(r"\s+", " ", item["title"]).strip()
        if not title or len(title) > 280:
            continue
        time_line = item.get("timeLine", "")
        m = re.search(
            r"(?P<h>\d{1,2}):(?P<m>\d{2})\s+(?P<mon>[A-Za-z]{3})\s+(?P<d>\d{1,2})(?:\s+(?P<y>\d{4}))?",
            time_line,
        )
        if not m:
            continue
        now_baku = datetime.now(BAKU)
        year = int(m.group("y") or now_baku.year)
        try:
            dt = datetime.strptime(
                f"{year} {m.group('mon')} {int(m.group('d'))} {int(m.group('h'))}:{m.group('m')}",
                "%Y %b %d %H:%M",
            ).replace(tzinfo=BAKU)
        except ValueError:
            continue
        ts = int(dt.timestamp())
        key = (title.lower(), ts)
        if key in unique:
            continue
        unique[key] = {
            "id": canonical_id(title, ts, "home-red"),
            "title": title,
            "description": "FinancialJuice /home — red economic-calendar event",
            "link": item.get("href", ""),
            "timestamp": ts,
            "source": "home",
            "impact": "red",
        }

    events = sorted(unique.values(), key=lambda x: x["timestamp"])
    return events[:MAX_HOME_EVENTS]


def run_pre_alerts(conn, home_events, now_ts):
    target = now_ts + PRE_ALERT_MINUTES * 60
    window = PRE_ALERT_WINDOW_SECONDS
    for event in home_events:
        if event.get("impact") != "red":
            continue
        if abs(event["timestamp"] - target) > window:
            continue
        key = f"pre:{event['id']}:{PRE_ALERT_MINUTES}"
        if was_sent(conn, key):
            continue

        local_dt = datetime.fromtimestamp(event["timestamp"], timezone.utc).astimezone(BAKU)
        title = html.escape(event["title"])
        message = (
            f"<b>⏰ 🔴 RED EVENT IN {PRE_ALERT_MINUTES} MINUTES</b>\n"
            f"<b>{title}</b>\n"
            f"🕒 {local_dt.strftime('%d.%m.%Y %H:%M')} Baku\n"
            f"🔴 FinancialJuice /home"
        )
        if event.get("link"):
            message += f'\n🔗 <a href="{html.escape(event["link"], quote=True)}">Открыть</a>'
        telegram_send(message)
        mark_sent(conn, key)


def main():
    conn = db()
    cleanup(conn)
    now_ts = int(time.time())
    now_local = datetime.fromtimestamp(now_ts, timezone.utc).astimezone(BAKU)

    print(f"Run at {now_local.strftime('%Y-%m-%d %H:%M:%S')} Baku")

    # 1) Primary source: live FinancialJuice /home red calendar.
    home_events = []
    try:
        home_events = scrape_financialjuice_home()
        print(f"FinancialJuice /home red calendar events: {len(home_events)}")
    except Exception as exc:
        print(f"WARNING: FinancialJuice /home scrape failed: {exc}")

    run_pre_alerts(conn, home_events, now_ts)
    run_daily_digest(conn, home_events, now_local)
    run_breaking_alerts(conn, home_events, now_ts)

    # 2) Optional RSS backup, but ONLY explicit RED/HIGH-IMPACT items.
    try:
        raw = fetch_url(RSS_URL)
        rss_items = [x for x in parse_rss(raw) if x.get("impact") == "red"]
        print(f"Explicit RED RSS items: {len(rss_items)}")
        run_breaking_alerts(conn, rss_items, now_ts)
    except Exception as exc:
        print(f"WARNING: FinancialJuice RSS unavailable: {exc}")

    conn.close()


if __name__ == "__main__":
    main()
