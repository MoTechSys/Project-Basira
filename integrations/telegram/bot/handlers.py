"""Telegram update handlers. Thin: read the message, call the Basira API, render, reply.

Privacy (ADR-004): message text and image bytes live only in local variables for the duration of one request;
images are downloaded into a ``BytesIO`` that is closed right after the API call. Logs carry the chat type, the
input kind, status counts, latency and error classes — never text, never user or chat ids.
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import logging
import re
import time
from collections import deque
from collections.abc import Mapping
from io import BytesIO
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType, MessageEntityType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot import render
from bot import strings_ar as txt
from bot.client import ApiError, ApiTimeoutError, BasiraClient, BasiraError, UnreachableError
from bot.config import IMAGE_MIME, MAX_IMAGE_BYTES, Settings

log = logging.getLogger("basira.bot")
_TAG = re.compile(r"<[^>]+>")
NEW_MESSAGE = filters.UpdateType.MESSAGE  # edits, channel posts and business messages are ignored


class RateLimiter:
    """Sliding one-minute window per user, in memory only (ids are never written anywhere)."""

    def __init__(self, per_minute: int, window: float = 60.0, clock: Any = time.monotonic) -> None:
        self.per_minute = per_minute
        self.window = window
        self._clock = clock
        self._hits: dict[int, deque[float]] = {}

    def allow(self, key: int) -> bool:
        now = self._clock()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        if len(self._hits) > 5000:  # bound memory: drop users idle for a full window
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                del self._hits[k]
        return True


def chat_kind(update: Update) -> str:
    chat = update.effective_chat
    return chat.type if chat else "unknown"


def plain(html_text: str) -> str:
    return html.unescape(_TAG.sub("", html_text))


class BasiraBot:
    def __init__(self, settings: Settings, client: BasiraClient) -> None:
        self.s = settings
        self.api = client
        self.limiter = RateLimiter(settings.user_rate_per_min)
        self.inflight = asyncio.Semaphore(8)

    # ------------------------------------------------------------------ wiring
    def register(self, app: Application[Any, Any, Any, Any, Any, Any]) -> None:
        cmd = NEW_MESSAGE & ~filters.VIA_BOT
        app.add_handler(CommandHandler("start", self.cmd_start, filters=cmd))
        app.add_handler(CommandHandler("help", self.cmd_help, filters=cmd))
        app.add_handler(CommandHandler("limits", self.cmd_limits, filters=cmd))
        app.add_handler(CommandHandler("sources", self.cmd_sources, filters=cmd))
        app.add_handler(CommandHandler("check", self.cmd_check, filters=cmd))
        private = NEW_MESSAGE & filters.ChatType.PRIVATE & ~filters.VIA_BOT
        groups = NEW_MESSAGE & filters.ChatType.GROUPS & ~filters.VIA_BOT
        image = filters.PHOTO | filters.Document.IMAGE
        app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_handler(MessageHandler(private & image, self.on_image))
        app.add_handler(MessageHandler(groups & filters.TEXT & ~filters.COMMAND, self.on_group_text))
        app.add_handler(
            MessageHandler(groups & image & filters.CaptionEntity(MessageEntityType.MENTION), self.on_image)
        )
        app.add_handler(MessageHandler(private & filters.COMMAND, self.on_unknown_command))
        app.add_handler(
            MessageHandler(private & ~filters.COMMAND & ~filters.TEXT & ~image, self.on_unsupported)
        )
        app.add_error_handler(self.on_error)

    # ------------------------------------------------------------------ helpers
    async def _messages(self) -> Mapping[str, Mapping[str, str]]:
        raw = await self.api.messages("ar")
        return {k: v for k, v in raw.items() if isinstance(v, dict)}

    async def _send(
        self, msg: Message, html_text: str, *, markup: InlineKeyboardMarkup | None = None
    ) -> Message:
        try:
            return await msg.reply_text(
                html_text, parse_mode=ParseMode.HTML, reply_markup=markup, do_quote=True
            )
        except BadRequest:  # an entity Telegram refuses to parse: same words, no formatting
            log.warning("html_rejected fallback=plain")
            return await msg.reply_text(plain(html_text), parse_mode=None, reply_markup=markup, do_quote=True)

    async def _edit(
        self, sent: Message, html_text: str, *, markup: InlineKeyboardMarkup | None = None
    ) -> None:
        try:
            await sent.edit_text(html_text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
            try:
                await sent.edit_text(plain(html_text), parse_mode=None, reply_markup=markup)
            except TelegramError:
                await sent.reply_text(plain(html_text), parse_mode=None, reply_markup=markup)

    def _site_button(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton(txt.OPEN_SITE, url=f"{self.s.web_url}/check")]])

    async def _deliver(self, sent: Message, pieces: list[str]) -> None:
        markup = self._site_button()
        last = len(pieces) - 1
        await self._edit(sent, pieces[0], markup=markup if last == 0 else None)
        for i, piece in enumerate(pieces[1:], 1):
            await self._send(sent, piece, markup=markup if i == last else None)

    async def _error_text(self, err: BasiraError) -> str:
        if isinstance(err, ApiError):
            text = render.esc(err.message_ar)
            return f"{text}\n{render.esc(txt.TRY_IN_A_MINUTE)}" if err.status == 429 else text
        if isinstance(err, ApiTimeoutError):
            return render.esc(txt.TIMEOUT)
        return render.esc(txt.UNREACHABLE)

    async def _limited(self, update: Update) -> bool:
        user = update.effective_user
        if user is None or self.limiter.allow(user.id):
            return False
        msg = update.effective_message
        if msg is not None:
            try:
                tpl = (await self._messages()).get("errors", {}).get("rate_limited", "")
            except BasiraError:
                tpl = ""
            await self._send(msg, render.esc(tpl) + ("\n" if tpl else "") + render.esc(txt.TRY_IN_A_MINUTE))
        log.info("chat=%s rate_limited=bot", chat_kind(update))
        return True

    # ------------------------------------------------------------------ checks
    async def check_text(self, update: Update, msg: Message, text: str, *, input_kind: str) -> None:
        text = text.strip()
        if not text:
            await self._send(
                msg,
                render.esc(txt.USAGE_GROUP if chat_kind(update) != ChatType.PRIVATE else txt.USAGE_PRIVATE),
            )
            return
        if await self._limited(update):
            return
        t0 = time.perf_counter()
        if len(text) > self.s.max_text:
            try:
                tpl = (await self._messages()).get("errors", {}).get("text_too_long", "")
                await self._send(msg, render.esc(render.fill(tpl, {"max": self.s.max_text})))
            except BasiraError as e:
                await self._send(msg, await self._error_text(e))
            log.info("chat=%s input=%s refused=too_long", chat_kind(update), input_kind)
            return
        sent = await self._send(msg, render.esc(txt.CHECKING))
        try:
            async with self.inflight:
                resp = await self.api.check(text)
                messages = await self._messages()
        except BasiraError as e:
            await self._edit(sent, await self._error_text(e))
            log.info(
                "chat=%s input=%s error=%s ms=%d", chat_kind(update), input_kind, type(e).__name__, _ms(t0)
            )
            return
        finally:
            del text
        await self._deliver(sent, render.render_check(resp, messages))
        log.info(
            "chat=%s input=%s quotes=%s refusal=%s ms=%d",
            chat_kind(update),
            input_kind,
            render.status_counts(resp),
            bool((resp.get("flags") or {}).get("refusal")),
            _ms(t0),
        )

    async def check_image(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE, msg: Message, source: Message
    ) -> None:
        if source.photo:
            file_id, mime, size = source.photo[-1].file_id, "image/jpeg", source.photo[-1].file_size
        elif source.document and (source.document.mime_type or "").lower() in IMAGE_MIME:
            file_id, mime, size = (
                source.document.file_id,
                (source.document.mime_type or "").lower(),
                source.document.file_size,
            )
        else:
            await self._send(msg, render.esc(txt.UNSUPPORTED))
            return
        if await self._limited(update):
            return
        t0 = time.perf_counter()
        if size is not None and size > MAX_IMAGE_BYTES:
            await self._send(msg, await self._too_large())
            log.info("chat=%s input=image refused=too_large", chat_kind(update))
            return
        sent = await self._send(msg, render.esc(txt.CHECKING_IMAGE))
        buf = BytesIO()
        try:
            tg_file = await ctx.bot.get_file(file_id)
            await tg_file.download_to_memory(buf)
            if buf.getbuffer().nbytes > MAX_IMAGE_BYTES:
                await self._edit(sent, await self._too_large())
                return
            async with self.inflight:
                resp = await self.api.check_image(buf.getvalue(), mime)
                messages = await self._messages()
        except BasiraError as e:
            await self._edit(sent, await self._error_text(e))
            log.info("chat=%s input=image error=%s ms=%d", chat_kind(update), type(e).__name__, _ms(t0))
            return
        except TelegramError as e:
            await self._edit(sent, render.esc(txt.UNREACHABLE))
            log.info("chat=%s input=image telegram_error=%s", chat_kind(update), type(e).__name__)
            return
        finally:
            buf.close()  # the bytes are released here; nothing was written to disk
        await self._deliver(sent, render.render_check(resp, messages, image=True))
        log.info(
            "chat=%s input=image quotes=%s ms=%d", chat_kind(update), render.status_counts(resp), _ms(t0)
        )

    async def _too_large(self) -> str:
        try:
            tpl = (await self._messages()).get("errors", {}).get("image_too_large", "")
        except BasiraError as e:
            return await self._error_text(e)
        return render.esc(render.fill(tpl, {"max_mb": MAX_IMAGE_BYTES // (1024 * 1024)}))

    # ------------------------------------------------------------------ commands
    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        parts = [txt.WELCOME]
        try:
            fixed = (await self._messages()).get("fixed", {})
            parts += [
                f"<i>{render.esc(fixed[k])}</i>"
                for k in ("transparency_notice", "privacy_notice")
                if k in fixed
            ]
        except BasiraError:
            pass
        await self._send(msg, "\n\n".join(parts), markup=self._site_button())

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        text = render.fill(
            txt.HELP, {"max_chars": self.s.max_text, "max_mb": MAX_IMAGE_BYTES // (1024 * 1024)}
        )
        try:
            footer = (await self._messages()).get("fixed", {}).get("footer")
            if footer:
                text += f"\n\n<i>{render.esc(footer)}</i>"
        except BasiraError:
            pass
        await self._send(msg, text)

    async def cmd_limits(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or await self._limited(update):
            return
        try:
            rules = await self.api.rules()
        except BasiraError as e:
            await self._send(msg, await self._error_text(e))
            return
        body = str(rules.get("text", ""))
        cut = body[:1500]
        if len(body) > 1500:
            cut = cut[: cut.rfind("\n")] if "\n" in cut else cut
            cut += "\n" + txt.ELLIPSIS
        more = render.fill(txt.LIMITS_MORE, {"url": f"{self.s.api_url}/v1/rules?ui_lang=ar"})
        await self._send(
            msg,
            f"{txt.LIMITS_HEADING}\n<blockquote expandable>{render.esc(cut)}</blockquote>\n{render.esc(more)}",
        )

    async def cmd_sources(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or await self._limited(update):
            return
        try:
            items = await self.api.sources()
        except BasiraError as e:
            await self._send(msg, await self._error_text(e))
            return
        lines = [render.fill(txt.SOURCES_HEADING, {"url": render.esc(self.s.api_url)})]
        for src in items:
            records = src.get("records")
            lines.append(
                render.fill(
                    txt.SOURCE_LINE,
                    {
                        "name": render.esc(str(src.get("name", ""))),
                        "version": render.esc(str(src.get("version", ""))),
                        "records": f"{records:,}" if isinstance(records, int) else "—",
                        "license": render.esc(str(src.get("license", ""))),
                    },
                )
            )
        for piece in render.pack([[render.Block(html=line) for line in lines]]):
            await self._send(msg, piece)

    async def cmd_check(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or _from_bot(msg):
            return
        rest = (msg.text or "").split(maxsplit=1)
        arg = rest[1] if len(rest) > 1 else ""
        target = msg.reply_to_message
        if arg.strip():
            await self.check_text(update, msg, arg, input_kind="command")
        elif target is not None and (target.photo or target.document):
            await self.check_image(update, ctx, msg, target)
        elif target is not None and (target.text or target.caption):
            await self.check_text(update, msg, target.text or target.caption or "", input_kind="reply")
        else:
            await self._send(
                msg,
                render.esc(txt.USAGE_GROUP if chat_kind(update) != ChatType.PRIVATE else txt.USAGE_PRIVATE),
            )

    # ------------------------------------------------------------------ messages
    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or _from_bot(msg):
            return
        kind = "forward" if msg.forward_origin else "text"
        await self.check_text(update, msg, msg.text or "", input_kind=kind)

    async def on_group_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Groups: act only when this bot is mentioned (privacy mode delivers nothing else but commands)."""
        msg = update.effective_message
        if msg is None or _from_bot(msg) or not self._mentioned(msg, ctx):
            return
        text = self._strip_mention(msg.text or "", ctx)
        target = msg.reply_to_message
        if not text.strip() and target is not None:
            if target.photo or target.document:
                await self.check_image(update, ctx, msg, target)
                return
            text = target.text or target.caption or ""
        await self.check_text(update, msg, text, input_kind="mention")

    async def on_image(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or _from_bot(msg):
            return
        if chat_kind(update) != ChatType.PRIVATE and not self._mentioned(msg, ctx):
            return
        await self.check_image(update, ctx, msg, msg)

    async def on_unknown_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is not None:
            await self._send(msg, render.esc(txt.USAGE_PRIVATE))

    async def on_unsupported(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is not None and not _from_bot(msg):
            await self._send(msg, render.esc(txt.UNSUPPORTED))

    async def on_error(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        err = ctx.error
        log.error("handler_error=%s", type(err).__name__)
        if isinstance(err, Forbidden):  # blocked by the user / removed from the group: nothing to say
            return
        if isinstance(update, Update) and update.effective_message is not None:
            with contextlib.suppress(TelegramError):
                await update.effective_message.reply_text(txt.UNREACHABLE)

    # ------------------------------------------------------------------ mentions
    def _mentioned(self, msg: Message, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
        me = f"@{ctx.bot.username}".lower()
        ents = (
            msg.parse_entities([MessageEntityType.MENTION])
            if msg.text
            else msg.parse_caption_entities([MessageEntityType.MENTION])
        )
        return any(v.lower() == me for v in ents.values())

    def _strip_mention(self, text: str, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        return re.sub(rf"@{re.escape(ctx.bot.username)}\b", " ", text, flags=re.IGNORECASE)


def _from_bot(msg: Message) -> bool:
    return bool(msg.from_user and msg.from_user.is_bot)


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


__all__ = ["BasiraBot", "RateLimiter", "UnreachableError"]
