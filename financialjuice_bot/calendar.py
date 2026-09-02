import datetime as dt
import json
import urllib.parse
import urllib.request
from typing import Iterable, List

from .config import (
    CALENDAR_COUNTRIES,
    CALENDAR_MIN_IMPORTANCE,
    HTTP_TIMEOUT,
    TE_API_KEY,
)
from .filters import impact_for
from .instruments import infer_currency, markets_for_currency
from .models import CalendarEvent

TE_BASE = "https://api.tradingeconomics.com/calendar/country"


def _iso(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
            try:
                parsed = dt.datetime.strptime(raw, fmt).replace(tzinfo=dt.timezone.utc)
                break
            except ValueError:
                continue
        else:
            return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp())


def _request_json(url: str) -> list:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PoladliFX-Calendar-Bot/2.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
        body = response.read()
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Trading Economics calendar response is not a list")
    return payload


def fetch_calendar(
    now_utc: dt.datetime,
    enabled_markets: Iterable[str],
    lookback_hours: int,
    lookahead_hours: int,
) -> List[CalendarEvent]:
    if not TE_API_KEY:
        raise RuntimeError(
            "TRADING_ECONOMICS_API_KEY is not configured. "
            "A licensed API key is required for the calendar provider."
        )
    start = (now_utc - dt.timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")
    end = (now_utc + dt.timedelta(hours=lookahead_hours)).strftime("%Y-%m-%d")
    country_path = ",".join(urllib.parse.quote(c.strip(), safe="") for c in CALENDAR_COUNTRIES)
    query = urllib.parse.urlencode(
        {
            "c": TE_API_KEY,
            "importance": str(CALENDAR_MIN_IMPORTANCE),
            "values": "true",
            "f": "json",
        }
    )
    # TE supports /calendar/country/{country}/{from}/{to}; comma-separated countries
    # are accepted by its calendar endpoints.
    url = f"{TE_BASE}/{country_path}/{start}/{end}?{query}"
    rows = _request_json(url)
    events: List[CalendarEvent] = []
    for row in rows:
        ts = _iso(str(row.get("Date", "")))
        if not ts:
            continue
        currency = infer_currency(str(row.get("Country", "")), str(row.get("Currency", "")))
        event_name = str(row.get("Event") or row.get("Category") or "").strip()
        importance = int(row.get("Importance") or 1)
        markets = markets_for_currency(currency, enabled_markets)
        if not markets:
            continue
        event_id = str(row.get("CalendarID") or row.get("CalendarId") or "")
        if not event_id:
            event_id = f"{row.get('Country','')}|{event_name}|{ts}"
        events.append(
            CalendarEvent(
                event_id=event_id,
                timestamp_utc=ts,
                country=str(row.get("Country") or ""),
                currency=currency,
                event_name=event_name,
                category=str(row.get("Category") or ""),
                impact=impact_for(event_name, importance),
                actual=str(row.get("Actual") or ""),
                forecast=str(row.get("Forecast") or ""),
                previous=str(row.get("Previous") or ""),
                revised_previous=str(row.get("Revised") or ""),
                source=str(row.get("Source") or "Trading Economics"),
                source_url=str(row.get("SourceURL") or ""),
                unit=str(row.get("Unit") or ""),
                importance=importance,
                last_update=str(row.get("LastUpdate") or ""),
                reference=str(row.get("Reference") or ""),
                markets=markets,
            )
        )
    return sorted(events, key=lambda x: x.timestamp_utc)


def fingerprint(event: CalendarEvent) -> str:
    return "|".join(
        [
            event.event_id,
            event.timestamp_utc.__str__(),
            event.actual,
            event.forecast,
            event.previous,
            event.revised_previous,
            event.last_update,
        ]
    )
