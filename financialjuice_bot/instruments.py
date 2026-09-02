from typing import Dict, Iterable, Tuple

MARKET_CURRENCY_MAP: Dict[str, Tuple[str, ...]] = {
    "XAUUSD": ("USD",),
    "DXY": ("USD",),
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USDCAD": ("USD", "CAD"),
}

COUNTRY_CURRENCY = {
    "united states": "USD",
    "euro area": "EUR",
    "european union": "EUR",
    "germany": "EUR",
    "france": "EUR",
    "italy": "EUR",
    "spain": "EUR",
    "netherlands": "EUR",
    "united kingdom": "GBP",
    "japan": "JPY",
    "canada": "CAD",
    "australia": "AUD",
    "new zealand": "NZD",
    "switzerland": "CHF",
}


def markets_for_currency(currency: str, enabled_markets: Iterable[str]) -> Tuple[str, ...]:
    currency = (currency or "").upper()
    enabled = set(enabled_markets)
    result = []
    for market in enabled:
        if currency in MARKET_CURRENCY_MAP.get(market, ()):
            result.append(market)
    return tuple(sorted(result))


def infer_currency(country: str, explicit_currency: str = "") -> str:
    raw = (explicit_currency or "").upper()
    if raw in {"USD", "$", "US$"}:
        return "USD"
    if raw in {"EUR", "€"}:
        return "EUR"
    if raw in {"GBP", "£"}:
        return "GBP"
    if raw in {"JPY", "¥"}:
        return "JPY"
    if raw in {"CAD", "C$"}:
        return "CAD"
    if raw in {"AUD", "A$"}:
        return "AUD"
    if raw in {"NZD", "NZ$"}:
        return "NZD"
    if raw in {"CHF"}:
        return "CHF"
    return COUNTRY_CURRENCY.get((country or "").strip().lower(), raw)
