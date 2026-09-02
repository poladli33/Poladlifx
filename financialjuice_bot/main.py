#!/usr/bin/env python3
import datetime as dt
import sys
import time

from .alerts import (
    format_actual,
    format_news,
    format_pre_event,
    pre_alert_key,
    should_fire_pre_alert,
)
from .calendar import fetch_calendar, fingerprint
from .config import (
    ALERT_15M,
    ALERT_30M,
    ALERT_5M,
    ALERT_ACTUAL,
    CALENDAR_LOOKAHEAD_HOURS,
    CALENDAR_LOOKBACK_HOURS,
    ENABLE_CALENDAR,
    ENABLE_NEWS,
    LOOKBACK_MINUTES,
    MARKETS,
    STATE_PATH,
    STATE_RETENTION_DAYS,
)
from .news import fetch_rss, parse_rss
from .storage import StateStore
from .telegram import send


def run() -> int:
    now = int(time.time())
    state = StateStore(STATE_PATH)
    state.prune(STATE_RETENTION_DAYS)
    failures = 0

    if ENABLE_NEWS:
        try:
            items = parse_rss(fetch_rss())
            cutoff = now - LOOKBACK_MINUTES * 60
            candidates = [
                item
                for item in items
                if item.timestamp_utc >= cutoff and not state.sent(f"news:{item.event_id}")
            ]
            candidates.sort(key=lambda item: item.timestamp_utc)
            print(f"NEWS: fetched={len(items)} new={len(candidates)}")
            for item in candidates:
                send(format_news(item))
                state.mark_sent(f"news:{item.event_id}")
        except Exception as exc:
            failures += 1
            print(f"NEWS ERROR: {exc}", file=sys.stderr)

    if ENABLE_CALENDAR:
        now_utc = dt.datetime.now(dt.timezone.utc)
        try:
            events = fetch_calendar(
                now_utc=now_utc,
                enabled_markets=MARKETS,
                lookback_hours=CALENDAR_LOOKBACK_HOURS,
                lookahead_hours=CALENDAR_LOOKAHEAD_HOURS,
            )
            print(f"CALENDAR: relevant_events={len(events)}")
            for event in events:
                state.update_calendar_seen(event.event_id, fingerprint(event))
                for minutes, enabled in ((30, ALERT_30M), (15, ALERT_15M), (5, ALERT_5M)):
                    if not enabled:
                        continue
                    key = pre_alert_key(event.event_id, minutes)
                    if state.sent(key):
                        continue
                    if should_fire_pre_alert(event, now, minutes):
                        send(format_pre_event(event, minutes))
                        state.mark_sent(key)

                if ALERT_ACTUAL and event.timestamp_utc <= now and event.actual and not state.actual_sent(event.event_id):
                    send(format_actual(event))
                    state.mark_actual_sent(event.event_id)
        except Exception as exc:
            failures += 1
            print(f"CALENDAR ERROR: {exc}", file=sys.stderr)

    state.save()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
