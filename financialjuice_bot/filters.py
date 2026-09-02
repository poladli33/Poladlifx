import html
import re
from typing import Optional, Tuple

from .models import ActualVerdict

EXTREME_RE = re.compile(
    r"\b(fomc|fed funds|federal funds rate|cpi|core cpi|pce|core pce|"
    r"non[- ]?farm payrolls?|nfp|powell|fed chair|rate decision|interest rate decision|"
    r"ecb rate decision|boe rate decision|boj rate decision|bank of canada rate|"
    r"tariff|emergency rate decision)\b",
    re.I,
)
HIGH_RE = re.compile(
    r"\b(gdp|ppi|core ppi|ism|pmi|retail sales|jobless claims?|unemployment|"
    r"jolts|adp employment|consumer confidence|manufacturing|services pmi|"
    r"opec|treasury auction|central bank|ecb|boe|boj|bank of canada)\b",
    re.I,
)
MEDIUM_RE = re.compile(
    r"\b(housing|durable goods|industrial production|trade balance|consumer sentiment|"
    r"building permits|new home sales|existing home sales|inventories)\b",
    re.I,
)

# Direction of a release relative to market interpretation. For neutral metrics the
# function intentionally returns ABOVE/BELOW instead of inventing a "better" label.
HIGHER_IS_BETTER = re.compile(
    r"\b(gdp|retail sales|industrial production|manufacturing|services pmi|pmi|"
    r"consumer confidence|consumer sentiment|adp employment|non[- ]?farm payrolls?|nfp|"
    r"jolts|job openings|building permits|new home sales|existing home sales)\b",
    re.I,
)
LOWER_IS_BETTER = re.compile(
    r"\b(cpi|core cpi|pce|core pce|ppi|core ppi|unemployment|jobless claims?|"
    r"initial jobless claims|continuing jobless claims|inflation)\b",
    re.I,
)


def impact_for(event_name: str, provider_importance: int = 1) -> str:
    name = event_name or ""
    if EXTREME_RE.search(name):
        return "EXTREME"
    if provider_importance >= 3 or HIGH_RE.search(name):
        return "HIGH"
    if provider_importance >= 2 or MEDIUM_RE.search(name):
        return "MEDIUM"
    return "LOW"


def _number(raw: str) -> Optional[float]:
    if raw is None:
        return None
    s = html.unescape(str(raw)).strip().replace(",", "")
    if not s or s in {"-", "—", "N/A", "NA", "n/a"}:
        return None
    multiplier = 1.0
    if re.search(r"[Kk]", s):
        multiplier = 1_000.0
    elif re.search(r"[Mm]", s):
        multiplier = 1_000_000.0
    elif re.search(r"[Bb]", s):
        multiplier = 1_000_000_000.0
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0)) * multiplier
    except ValueError:
        return None


def actual_vs_forecast(event_name: str, actual: str, forecast: str) -> ActualVerdict:
    a = _number(actual)
    f = _number(forecast)
    if a is None or f is None:
        return ActualVerdict("NO COMPARISON", "unknown", None)
    delta = a - f
    # Treat tiny deviations as in-line. The tolerance is deliberately relative for
    # large releases and absolute for small values, avoiding unstable labels such as
    # 0.01 vs 0.011 becoming "much worse".
    denom = max(abs(f), 1.0)
    relative = abs(delta) / denom
    in_line = relative <= 0.01 or abs(delta) <= 0.01
    if in_line:
        return ActualVerdict("IN LINE", "neutral", delta)

    if HIGHER_IS_BETTER.search(event_name or ""):
        better = delta > 0
    elif LOWER_IS_BETTER.search(event_name or ""):
        better = delta < 0
    else:
        return ActualVerdict("ABOVE FORECAST" if delta > 0 else "BELOW FORECAST", "unknown", delta)

    # "Much" is a configurable heuristic; 2%+ relative deviation is enough to be
    # materially different for this alerting use case.
    much = relative >= 0.02
    if better:
        return ActualVerdict("🟢 MUCH BETTER" if much else "🟢 BETTER", "better", delta)
    return ActualVerdict("🔴 MUCH WORSE" if much else "🔴 WORSE", "worse", delta)


def news_impact(text: str) -> str:
    if EXTREME_RE.search(text):
        return "EXTREME"
    if HIGH_RE.search(text):
        return "HIGH"
    if MEDIUM_RE.search(text):
        return "MEDIUM"
    return "LOW"
