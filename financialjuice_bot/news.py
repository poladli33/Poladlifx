import email.utils
import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import List

from .config import FINANCIALJUICE_RSS_URL, HTTP_TIMEOUT, MAX_NEWS_ITEMS
from .models import NewsItem


def fetch_rss() -> bytes:
    request = urllib.request.Request(
        FINANCIALJUICE_RSS_URL,
        headers={
            "User-Agent": "PoladliFX-FinancialJuice-Bot/2.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return response.read()


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value or "")
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def parse_date(value: str) -> int:
    if not value:
        return int(time.time())
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return int(dt.replace(tzinfo=__import__("datetime").timezone.utc).timestamp())
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        return int(time.time())


def parse_rss(raw: bytes) -> List[NewsItem]:
    root = ET.fromstring(raw)
    result: List[NewsItem] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        description = strip_html(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        pub = (item.findtext("pubDate") or "").strip()
        result.append(
            NewsItem(
                event_id=guid,
                title=title,
                description=description,
                link=link,
                timestamp_utc=parse_date(pub),
            )
        )
    result.sort(key=lambda x: x.timestamp_utc, reverse=True)
    return result[:MAX_NEWS_ITEMS]
