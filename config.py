"""Configuration loading and validation.

All secrets and settings come from environment variables (optionally loaded
from a local .env file via python-dotenv). Nothing here is hardcoded.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if present. In production (Docker,
# Railway, Render, etc.) the platform injects real environment variables and
# this is simply a no-op if no .env file exists.
load_dotenv()

_NUMERIC_CHANNEL_ID_RE = re.compile(r"^-?\d+$")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _require(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigError(
            f"Переменная окружения {name} не задана. "
            f"Проверь файл .env (см. .env.example)."
        )
    return value.strip()


def parse_channel_id(raw: str) -> str | int:
    """Normalize CHANNEL_ID into the form expected by the Bot API.

    Supports:
      * public channel username, e.g. ``@my_channel``
      * numeric channel id, e.g. ``-1001234567890``

    Returns an ``int`` for numeric ids (required by aiogram/Bot API for
    private channels) and a ``str`` for ``@username`` ids.
    """
    value = raw.strip()
    if not value:
        raise ConfigError("CHANNEL_ID не может быть пустым.")

    if value.startswith("@"):
        return value

    if _NUMERIC_CHANNEL_ID_RE.match(value):
        return int(value)

    # Fallback: treat as a bare username without leading "@".
    return f"@{value}"


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    channel_id: str | int
    channel_id_raw: str
    channel_url: str
    pdf_path: Path
    bot_username: str

    @property
    def deep_link(self) -> str:
        return f"https://t.me/{self.bot_username}?start=guide"


def load_settings() -> Settings:
    """Read and validate all required environment variables.

    Raises ConfigError with a human-readable (Russian) message when
    something required is missing, so the failure is easy to diagnose from
    logs without leaking secrets.
    """
    token = _require("TELEGRAM_BOT_TOKEN")
    channel_id_raw = _require("CHANNEL_ID")
    channel_url = _require("CHANNEL_URL")
    pdf_path_raw = _require("PDF_PATH")
    bot_username = _require("BOT_USERNAME").lstrip("@")

    if not channel_url.startswith("https://t.me/"):
        raise ConfigError(
            "CHANNEL_URL должен быть ссылкой вида https://t.me/your_channel"
        )

    return Settings(
        telegram_bot_token=token,
        channel_id=parse_channel_id(channel_id_raw),
        channel_id_raw=channel_id_raw,
        channel_url=channel_url,
        pdf_path=Path(pdf_path_raw),
        bot_username=bot_username,
    )


def mask_token(token: str) -> str:
    """Return a safe-to-log representation of the bot token.

    Never log the full token. We only show the numeric bot id prefix
    (which is not secret — it is part of the bot's public @-link/API url)
    and mask the rest.
    """
    if ":" not in token:
        return "***"
    bot_id, _secret = token.split(":", 1)
    return f"{bot_id}:***"
