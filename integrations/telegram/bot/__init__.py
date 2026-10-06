"""Basira Telegram bot — a thin client over the public Basira API (POST /v1/check, /v1/check/image).

The bot holds no model, writes no religious text and stores nothing: every word shown about a quotation comes
from the API response or from ``messages/*.json`` (served at ``GET /v1/messages/{lang}``).
"""

__version__ = "0.1.0"
