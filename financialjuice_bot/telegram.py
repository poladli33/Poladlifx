import json
import urllib.parse
import urllib.request

from .config import DRY_RUN, HTTP_TIMEOUT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send(message: str) -> None:
    if DRY_RUN:
        print("\n--- TELEGRAM DRY RUN ---\n" + message + "\n--- END ---")
        return
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            raise RuntimeError(f"Telegram HTTP {response.status}: {raw[:300]}")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Telegram returned non-JSON response") from exc
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
