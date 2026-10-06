"""Runtime settings, read once from the environment (see .env.example). Nothing here is ever logged."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_API = "https://basirapp.site"
DEFAULT_HEARTBEAT = "/tmp/basira-bot.heartbeat"  # liveness stamp only, no user data
_TOKEN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

# Limits mirror the API contract (docs/API.md §1, §6) so oversized input is refused before any request.
MAX_TEXT_CHARS = 5000
MAX_IMAGE_BYTES = 6 * 1024 * 1024
IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})


class ConfigError(ValueError):
    """Raised for a missing or malformed setting; the message never contains the value."""


def _url(name: str, value: str) -> str:
    u = urlparse(value)
    if u.scheme not in {"http", "https"} or not u.netloc:
        raise ConfigError(f"{name} must be an http(s) URL")
    return value.rstrip("/")


def _int(env: Mapping[str, str], name: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer") from e
    if not lo <= v <= hi:
        raise ConfigError(f"{name} must be in [{lo}, {hi}]")
    return v


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    api_url: str = DEFAULT_API
    web_url: str = DEFAULT_API
    eval_key: str = ""
    max_text: int = MAX_TEXT_CHARS
    text_timeout: float = 30.0
    image_timeout: float = 60.0
    user_rate_per_min: int = 10
    webhook_url: str = ""
    webhook_secret: str = ""
    port: int = 8080
    heartbeat_file: str = DEFAULT_HEARTBEAT

    def __repr__(self) -> str:  # never print secrets
        return f"Settings(api_url={self.api_url!r}, webhook={'on' if self.webhook_url else 'off'})"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        token = e.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not _TOKEN.match(token):
            raise ConfigError("TELEGRAM_BOT_TOKEN is missing or malformed (get one from @BotFather)")
        webhook_url = e.get("TELEGRAM_WEBHOOK_URL", "").strip()
        secret = e.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
        if webhook_url:
            _url("TELEGRAM_WEBHOOK_URL", webhook_url)
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", secret):
                raise ConfigError(
                    "TELEGRAM_WEBHOOK_SECRET must be 16-256 chars of [A-Za-z0-9_-] in webhook mode"
                )
        return cls(
            token=token,
            api_url=_url("BASIRA_API_URL", e.get("BASIRA_API_URL", "").strip() or DEFAULT_API),
            web_url=_url("BASIRA_WEB_URL", e.get("BASIRA_WEB_URL", "").strip() or DEFAULT_API),
            eval_key=e.get("BASIRA_EVAL_KEY", "").strip(),
            max_text=_int(e, "MAX_TEXT", MAX_TEXT_CHARS, 1, MAX_TEXT_CHARS),
            user_rate_per_min=_int(e, "BOT_RATE_PER_MIN", 10, 1, 120),
            webhook_url=webhook_url,
            webhook_secret=secret,
            port=_int(e, "PORT", 8080, 1, 65535),
            heartbeat_file=e.get("BOT_HEARTBEAT_FILE", "").strip() or DEFAULT_HEARTBEAT,
        )
