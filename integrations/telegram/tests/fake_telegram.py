"""A fake Telegram Bot API for tests: the real python-telegram-bot ``Application`` (filters, routing, handlers)
runs unmodified; only the HTTPS transport to api.telegram.org is replaced by this in-memory recorder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from telegram import Update
from telegram.request import BaseRequest, RequestData

BOT_ID = 8949966941
BOT_USERNAME = "BasiraCheckBot"
TOKEN = "1234567:TESTONLY-not-a-real-token-000000000"  # 7-digit id: never matches the secret scan
DOC_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128  # valid PNG signature


@dataclass
class Call:
    method: str
    params: dict[str, Any]


@dataclass
class FakeTelegram(BaseRequest):
    calls: list[Call] = field(default_factory=list)
    file_bytes: bytes = DOC_BYTES
    next_message_id: int = 1000
    fail_html_once: bool = False

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    @property
    def read_timeout(self) -> float | None:
        return 5.0

    def sent(self, method: str | None = None) -> list[Call]:
        return [c for c in self.calls if method is None or c.method == method]

    def texts(self) -> list[str]:
        """Final text of every bot message (edits replace the placeholder)."""
        out: dict[int, str] = {}
        order: list[int] = []
        for c in self.calls:
            if c.method == "sendMessage":
                mid = int(c.params["_id"])
                out[mid] = str(c.params["text"])
                order.append(mid)
            elif c.method == "editMessageText":
                out[int(c.params["message_id"])] = str(c.params["text"])
        return [out[i] for i in order]

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: RequestData | None = None,
        read_timeout: Any = None,
        write_timeout: Any = None,
        connect_timeout: Any = None,
        pool_timeout: Any = None,
    ) -> tuple[int, bytes]:
        if "/file/bot" in url:
            return 200, self.file_bytes
        endpoint = url.rsplit("/", 1)[-1]
        params: dict[str, Any] = {}
        if request_data is not None:
            params = {k: _decode(v) for k, v in request_data.json_parameters.items()}
        result: Any
        if endpoint == "getMe":
            result = {
                "id": BOT_ID,
                "is_bot": True,
                "first_name": "بصيرة | Basira",
                "username": BOT_USERNAME,
                "can_join_groups": True,
                "can_read_all_group_messages": False,
                "supports_inline_queries": False,
            }
        elif endpoint == "getFile":
            result = {
                "file_id": params["file_id"],
                "file_unique_id": "u",
                "file_size": len(self.file_bytes),
                "file_path": "photos/file_0.png",
            }
        elif endpoint in {"sendMessage", "editMessageText"}:
            if self.fail_html_once and params.get("parse_mode") == "HTML":
                self.fail_html_once = False
                self.calls.append(Call(endpoint + ":rejected", params))
                body = {"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities"}
                return 400, json.dumps(body).encode()
            if endpoint == "sendMessage":
                self.next_message_id += 1
                params["_id"] = self.next_message_id
                mid = self.next_message_id
            else:
                mid = int(params["message_id"])
            result = {
                "message_id": mid,
                "date": 0,
                "chat": {"id": int(params["chat_id"]), "type": "private"},
                "text": params["text"],
                "from": {"id": BOT_ID, "is_bot": True, "first_name": "B"},
            }
        else:
            result = True
        self.calls.append(Call(endpoint, params))
        return 200, json.dumps({"ok": True, "result": result}).encode()


def _decode(v: str) -> Any:
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


# ------------------------------------------------------------------ update builders
_uid = 0


def _next() -> int:
    global _uid  # noqa: PLW0603 — test-only counter
    _uid += 1
    return _uid


def user(uid: int = 42) -> dict[str, Any]:
    return {"id": uid, "is_bot": False, "first_name": "U"}


def chat(kind: str = "private", cid: int = 42) -> dict[str, Any]:
    c: dict[str, Any] = {"id": cid if kind == "private" else -100123, "type": kind}
    if kind != "private":
        c["title"] = "G"
    return c


def entities_for(text: str) -> list[dict[str, Any]]:
    ents: list[dict[str, Any]] = []
    if text.startswith("/"):
        cmd = text.split(maxsplit=1)[0]
        ents.append({"type": "bot_command", "offset": 0, "length": len(cmd.encode("utf-16-le")) // 2})
    at = f"@{BOT_USERNAME}"
    i = text.find(at)
    if i >= 0:
        off = len(text[:i].encode("utf-16-le")) // 2
        ents.append({"type": "mention", "offset": off, "length": len(at)})
    return ents


def message(
    text: str | None = None,
    *,
    kind: str = "private",
    uid: int = 42,
    photo: bool = False,
    document_mime: str | None = None,
    file_size: int = 1000,
    caption: str | None = None,
    forward: bool = False,
    reply_to: dict[str, Any] | None = None,
    from_bot: bool = False,
) -> dict[str, Any]:
    m: dict[str, Any] = {"message_id": _next(), "date": 0, "chat": chat(kind, uid), "from": user(uid)}
    if from_bot:
        m["from"] = {"id": 777, "is_bot": True, "first_name": "OtherBot"}
    if text is not None:
        m["text"] = text
        ents = entities_for(text)
        if ents:
            m["entities"] = ents
    if photo:
        m["photo"] = [
            {"file_id": "small", "file_unique_id": "s", "width": 90, "height": 90, "file_size": 100},
            {"file_id": "big", "file_unique_id": "b", "width": 900, "height": 900, "file_size": file_size},
        ]
    if document_mime:
        m["document"] = {
            "file_id": "doc",
            "file_unique_id": "d",
            "mime_type": document_mime,
            "file_size": file_size,
        }
    if caption is not None:
        m["caption"] = caption
        ents = entities_for(caption)
        if ents:
            m["caption_entities"] = ents
    if forward:
        m["forward_origin"] = {
            "type": "channel",
            "date": 0,
            "chat": {"id": -1001, "type": "channel", "title": "C"},
            "message_id": 5,
        }
    if reply_to is not None:
        m["reply_to_message"] = reply_to
    return m


def update(msg: dict[str, Any], bot: Any, *, edited: bool = False) -> Update:
    key = "edited_message" if edited else "message"
    if edited:
        msg = {**msg, "edit_date": 1}
    u = Update.de_json({"update_id": _next(), key: msg}, bot)
    assert u is not None
    return u
