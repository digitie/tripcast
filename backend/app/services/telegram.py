"""텔레그램 Bot API 래퍼."""
from __future__ import annotations

import httpx


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> dict:
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            r.raise_for_status()
            return r.json()
