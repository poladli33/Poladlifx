from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class NewsItem:
    event_id: str
    title: str
    description: str
    link: str
    timestamp_utc: int
    source: str = "FinancialJuice"


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    timestamp_utc: int
    country: str
    currency: str
    event_name: str
    category: str = ""
    impact: str = "LOW"
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    revised_previous: str = ""
    source: str = "Trading Economics"
    source_url: str = ""
    unit: str = ""
    importance: int = 1
    last_update: str = ""
    reference: str = ""
    markets: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ActualVerdict:
    label: str
    direction: str
    delta: Optional[float]
