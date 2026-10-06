"""End-to-end through the real python-telegram-bot Application: filters → handlers → Basira client → render.

Telegram is faked at the HTTP layer (fake_telegram.FakeTelegram) and the Basira API with httpx.MockTransport,
so routing, entity parsing, edits and splitting are exercised exactly as in production.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from telegram.ext import Application, ApplicationBuilder

from bot import render
from bot import strings_ar as txt
from bot.client import BasiraClient
from bot.config import MAX_IMAGE_BYTES, Settings
from bot.handlers import BasiraBot, RateLimiter

from conftest import api_transport, load, messages_map
from fake_telegram import BOT_USERNAME, TOKEN, FakeTelegram, message, update

M = messages_map()
QURAN = "قال تعالى: ﴿إن الله مع الصابرين﴾"


@dataclass
class Harness:
    app: Application[Any, Any, Any, Any, Any, Any]
    tg: FakeTelegram
    api_log: list[httpx.Request]

    async def send(self, msg: dict[str, Any], *, edited: bool = False) -> list[str]:
        before = len(self.tg.texts())
        await self.app.process_update(update(msg, self.app.bot, edited=edited))
        return self.tg.texts()[before:]

    def api_paths(self) -> list[str]:
        return [r.url.path for r in self.api_log if r.url.path != "/v1/messages/ar"]


Factory = Callable[..., Any]


@pytest.fixture
async def make() -> AsyncIterator[Factory]:
    apps: list[Application[Any, Any, Any, Any, Any, Any]] = []

    async def factory(
        routes: dict[str, Any] | None = None, *, rate: int = 10, max_text: int = 5000
    ) -> Harness:
        tg = FakeTelegram()
        log: list[httpx.Request] = []
        settings = Settings(token=TOKEN, user_rate_per_min=rate, max_text=max_text)
        client = BasiraClient("https://api.test", transport=api_transport(routes or {}, log=log))
        app = ApplicationBuilder().token(TOKEN).request(tg).get_updates_request(FakeTelegram()).build()
        BasiraBot(settings, client).register(app)
        await app.initialize()
        apps.append(app)
        return Harness(app, tg, log)

    yield factory
    for a in apps:
        await a.shutdown()


# ------------------------------------------------------------------ private chat
async def test_start_has_welcome_transparency_privacy_and_site_button(make: Factory) -> None:
    h = await make()
    [out] = await h.send(message("/start"))
    assert "بصيرة" in out and "Forward" in out
    assert render.esc(M["fixed"]["transparency_notice"]) in out
    assert render.esc(M["fixed"]["privacy_notice"]) in out
    markup = h.tg.sent("sendMessage")[0].params["reply_markup"]
    assert markup["inline_keyboard"][0][0]["url"] == "https://basirapp.site/check"


async def test_text_found_flow_placeholder_then_edit(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    [out] = await h.send(message(QURAN))
    assert h.tg.sent("sendMessage")[0].params["text"] == txt.CHECKING
    assert h.tg.sent("editMessageText"), "placeholder must be edited with the result"
    assert "✅" in out and M["labels"]["found"] in out
    assert load("found_quran")["quotes"][0]["matches"][0]["source_text"] in out
    assert h.tg.sent("sendMessage")[0].params["reply_parameters"]["message_id"] > 0  # replies to the user


async def test_forwarded_text_is_checked(make: Factory) -> None:
    h = await make({"/v1/check": "needs_review_quran"})
    [out] = await h.send(message("قال تعالى: ﴿إن الله علي كل شيء قدير﴾", forward=True))
    assert "<b>علي</b>" in out and "⚠️" in out


async def test_refusal_shows_only_the_refusal_notice(make: Factory) -> None:
    h = await make({"/v1/check": "refusal"})
    [out] = await h.send(message("ما حكم صلاة الجمعة؟"))
    assert out == f"ℹ️ {render.esc(M['notice']['refusal'])}"


async def test_no_quotes(make: Factory) -> None:
    h = await make({"/v1/check": "no_quotes"})
    [out] = await h.send(message("اليوم طقس جميل"))
    assert render.esc(M["notice"]["no_quotes"]) in out


async def test_too_long_is_refused_without_calling_the_api(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    [out] = await h.send(message("ا" * 5001))
    assert out == render.esc(M["errors"]["text_too_long"].replace("{max}", "5000"))
    assert h.api_paths() == []


@pytest.mark.parametrize(
    ("status", "code", "extra"),
    [
        (413, "text_too_long", ""),
        (422, "invalid_input", ""),
        (429, "rate_limited", txt.TRY_IN_A_MINUTE),
        (503, "degraded", ""),
    ],
)
async def test_api_errors_use_message_ar_verbatim(make: Factory, status: int, code: str, extra: str) -> None:
    body = {"error": {"code": code, "message_ar": M["errors"][code], "message_en": "x"}}
    h = await make({"/v1/check": (status, body)})
    [out] = await h.send(message(QURAN))
    assert out.startswith(render.esc(M["errors"][code]))
    assert (extra in out) if extra else out == render.esc(M["errors"][code])


async def test_api_down_and_timeout_are_reported_honestly(make: Factory) -> None:
    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("x")

    def slow(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("x")

    h = await make({"/v1/check": down})
    assert (await h.send(message(QURAN))) == [render.esc(txt.UNREACHABLE)]
    h = await make({"/v1/check": slow})
    assert (await h.send(message(QURAN))) == [render.esc(txt.TIMEOUT)]


async def test_whitespace_only_message_is_not_sent(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    [out] = await h.send(message("   \n  "))
    assert out == render.esc(txt.USAGE_PRIVATE) and h.api_paths() == []


async def test_photo_goes_to_image_endpoint_ocr_shown_never_found(make: Factory) -> None:
    h = await make({"/v1/check/image": "image_hadith"})
    [out] = await h.send(message(photo=True))
    assert h.tg.sent("sendMessage")[0].params["text"] == txt.CHECKING_IMAGE
    assert h.api_paths() == ["/v1/check/image"]
    req = next(r for r in h.api_log if r.url.path == "/v1/check/image")
    assert h.tg.file_bytes in req.content and b'filename="image.jpg"' in req.content
    assert txt.OCR_HEADING in out and "⚠️" in out and "✅" not in out


async def test_image_document_png_and_unsupported_document(make: Factory) -> None:
    h = await make({"/v1/check/image": "image_hadith"})
    await h.send(message(document_mime="image/png"))
    req = next(r for r in h.api_log if r.url.path == "/v1/check/image")
    assert b"Content-Type: image/png" in req.content
    [out] = await h.send(message(document_mime="application/pdf"))
    assert out == render.esc(txt.UNSUPPORTED)


async def test_oversized_image_is_refused_before_download(make: Factory) -> None:
    h = await make({"/v1/check/image": "image_hadith"})
    [out] = await h.send(message(photo=True, file_size=MAX_IMAGE_BYTES + 1))
    assert out == render.esc(M["errors"]["image_too_large"].replace("{max_mb}", "6"))
    assert not h.tg.sent("getFile") and h.api_paths() == []


async def test_sticker_or_voice_gets_unsupported(make: Factory) -> None:
    h = await make()
    msg = message()
    msg["voice"] = {"file_id": "v", "file_unique_id": "v", "duration": 1}
    assert (await h.send(msg)) == [render.esc(txt.UNSUPPORTED)]


async def test_limits_and_sources(make: Factory) -> None:
    h = await make({"/v1/rules": "rules", "/v1/sources": "sources"})
    [lim] = await h.send(message("/limits"))
    assert txt.LIMITS_HEADING in lim and "expandable" in lim
    assert render.u16(lim) < 4096
    [src] = await h.send(message("/sources"))
    for s in load("sources"):
        assert render.esc(s["name"]) in src and render.esc(s["license"]) in src
    assert "Tanzil" in src and "Open-Hadith-Data" in src and "HadeethEnc" in src and "62,169" in src


async def test_long_result_is_split_and_button_only_on_last(make: Factory) -> None:
    resp = load("partial_hadith")
    resp["quotes"] = resp["quotes"] * 12
    h = await make({"/v1/check": (200, resp)})
    outs = await h.send(message("طلب العلم فريضة"))
    assert len(outs) > 1 and all(render.u16(o) <= 4096 for o in outs)
    with_button = [c for c in h.tg.calls if c.params.get("reply_markup")]
    assert len(with_button) == 1 and with_button[0] is h.tg.calls[-1]


async def test_html_rejected_by_telegram_falls_back_to_plain(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    h.tg.fail_html_once = True  # Telegram refuses the first HTML message (the placeholder)
    [out] = await h.send(message(QURAN))
    rejected = h.tg.sent("sendMessage:rejected")
    retried = h.tg.sent("sendMessage")[0]
    assert len(rejected) == 1 and rejected[0].params["text"] == txt.CHECKING
    assert retried.params["text"] == txt.CHECKING and "parse_mode" not in retried.params  # same words, plain
    assert "✅" in out  # the result still arrives


async def test_rate_limit_per_user(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"}, rate=2)
    await h.send(message(QURAN))
    await h.send(message(QURAN))
    [out] = await h.send(message(QURAN))
    assert txt.TRY_IN_A_MINUTE in out
    assert h.api_paths().count("/v1/check") == 2
    await h.send(message(QURAN, uid=99))  # another user is not affected
    assert h.api_paths().count("/v1/check") == 3


def test_rate_limiter_window() -> None:
    now = [0.0]
    rl = RateLimiter(2, clock=lambda: now[0])
    assert rl.allow(1) and rl.allow(1) and not rl.allow(1)
    now[0] = 60.0
    assert rl.allow(1)


# ------------------------------------------------------------------ groups
async def test_group_plain_text_is_ignored(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    assert (await h.send(message(QURAN, kind="supergroup"))) == []
    assert h.api_paths() == []


async def test_group_check_command_with_argument_and_as_reply(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran", "/v1/check/image": "image_hadith"})
    [a] = await h.send(message(f"/check@{BOT_USERNAME} {QURAN}", kind="supergroup"))
    assert "✅" in a
    original = message(QURAN, kind="supergroup", uid=7)
    [b] = await h.send(message("/check", kind="supergroup", reply_to=original))
    assert "✅" in b
    photo = message(photo=True, kind="supergroup", uid=7)
    [c] = await h.send(message("/check", kind="supergroup", reply_to=photo))
    assert txt.OCR_HEADING in c
    [d] = await h.send(message("/check", kind="supergroup"))
    assert d == render.esc(txt.USAGE_GROUP)


async def test_group_mention_checks_text_and_strips_the_mention(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    [out] = await h.send(message(f"@{BOT_USERNAME} {QURAN}", kind="group"))
    assert "✅" in out
    import json

    sent = json.loads(next(r for r in h.api_log if r.url.path == "/v1/check").content)
    assert BOT_USERNAME not in sent["text"] and QURAN in sent["text"]


async def test_group_photo_only_with_mention_in_caption(make: Factory) -> None:
    h = await make({"/v1/check/image": "image_hadith"})
    assert (await h.send(message(photo=True, kind="supergroup"))) == []
    [out] = await h.send(message(photo=True, kind="supergroup", caption=f"@{BOT_USERNAME}"))
    assert txt.OCR_HEADING in out


# ------------------------------------------------------------------ robustness
async def test_edits_and_other_bots_are_ignored(make: Factory) -> None:
    h = await make({"/v1/check": "found_quran"})
    assert (await h.send(message(QURAN), edited=True)) == []
    assert (await h.send(message(QURAN, from_bot=True))) == []
    assert h.api_paths() == []


async def test_logs_never_contain_user_text_or_ids(make: Factory, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="basira.bot")
    h = await make({"/v1/check": "found_quran", "/v1/check/image": "image_hadith"})
    secret = "قال تعالى: ﴿إن الله مع الصابرين﴾ 0555123456"
    await h.send(message(secret, uid=31337))
    await h.send(message(photo=True, uid=31337))
    logs = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("basira"))
    assert "الصابرين" not in logs and "0555123456" not in logs and "31337" not in logs
    assert "quotes={'found': 1}" in logs and "input=image" in logs


def test_settings_validation_and_repr_hides_secrets() -> None:
    from bot.config import ConfigError

    with pytest.raises(ConfigError):
        Settings.from_env({})
    with pytest.raises(ConfigError):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": TOKEN, "BASIRA_API_URL": "ftp://x"})
    with pytest.raises(ConfigError):
        Settings.from_env(
            {
                "TELEGRAM_BOT_TOKEN": TOKEN,
                "TELEGRAM_WEBHOOK_URL": "https://h",
                "TELEGRAM_WEBHOOK_SECRET": "short",
            }
        )
    s = Settings.from_env({"TELEGRAM_BOT_TOKEN": TOKEN, "BASIRA_EVAL_KEY": "k", "MAX_TEXT": "100"})
    assert s.max_text == 100 and TOKEN not in repr(s) and "k" not in repr(s).replace("webhook", "")
