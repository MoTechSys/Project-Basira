"""Live end-to-end check of a running bot, driven from a real Telegram *user* account (Telethon).

    TG_API_ID=… TG_API_HASH=… TG_SESSION_FILE=~/path/telegram_session.string \
    python scripts/live_e2e.py @BasiraCheckBot [--image path.png] [--forward-from @channel:msg_id]

The user session is read from a file outside the repository and never printed. Each scenario sends one message,
waits until the bot's placeholder is replaced by the final result, and asserts on the visible text. Prints one
line per scenario and exits non-zero on any failure. Requires: pip install telethon
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

PLACEHOLDERS = ("⏳",)


@dataclass
class Case:
    name: str
    text: str | None
    expect: tuple[str, ...]
    forbid: tuple[str, ...] = ()
    image: str | None = None
    forward: tuple[str, int] | None = None


CASES = [
    Case("start", "/start", ("بصيرة", "لا يكتب الذكاء الاصطناعي")),
    Case("found_quran", "قال تعالى: ﴿إن الله مع الصابرين﴾", ("✅", "وُجد", "سورة البقرة، الآية 153")),
    Case("needs_review_quran", "قال تعالى: ﴿إن الله علي كل شيء قدير﴾", ("⚠️", "يحتاج مراجعة", "علي")),
    Case("not_found_hadith", "قال ﷺ: «الدين المعاملة»", ("○", "لم يوجد في مصادرنا", "ابحث في الدرر السنية")),
    Case("partial_hadith", "قال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»", ("◐", "مطابقة جزئية", "سنن ابن ماجه")),
    Case("refusal", "ما حكم صلاة الجمعة؟", ("لا تجيب عن الأسئلة الشرعية",), ("✅", "⚠️")),
    Case("no_quotes", "اليوم طقس جميل", ("لم نعثر في هذا النص على آية أو حديث",)),
    Case("sources", "/sources", ("Tanzil", "Open-Hadith-Data", "HadeethEnc")),
    Case("limits", "/limits", ("حدود ما تفحصه بصيرة",)),
    Case("unsupported", None, ("أستقبل النصوص والصور فقط",)),  # a sticker-like non-image document
]
# Over-length text (> 5000) cannot be sent through Telegram (4096-char message cap); tests/test_handlers.py covers it.


async def final_reply(client: TelegramClient, bot: str, after_id: int, timeout: float = 90) -> str:
    """Concatenate the bot's replies after ``after_id`` once none of them is a placeholder any more."""
    deadline = time.monotonic() + timeout
    stable_since: float | None = None
    last = ""
    while time.monotonic() < deadline:
        await asyncio.sleep(1.5)
        msgs = [m for m in await client.get_messages(bot, limit=10) if m.id > after_id and not m.out]
        text = "\n---\n".join((m.message or "") for m in reversed(msgs))
        done = bool(msgs) and not any(text.lstrip().startswith(p) for p in PLACEHOLDERS) and all(
            not (m.message or "").startswith(PLACEHOLDERS) for m in msgs
        )
        if done and text == last:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 2:
                return text
        else:
            stable_since = None
        last = text
    return last


async def run(args: argparse.Namespace) -> int:
    session = Path(os.path.expanduser(os.environ["TG_SESSION_FILE"])).read_text().strip()
    client = TelegramClient(StringSession(session), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    await client.connect()
    if not await client.is_user_authorized():
        print("session not authorized", file=sys.stderr)
        return 2
    cases = list(CASES)
    if args.image:
        cases.append(Case("image", None, ("النص كما قُرئ من الصورة", "⚠️"), ("✅",), image=args.image))
    if args.forward_from:
        chat, _, mid = args.forward_from.rpartition(":")
        cases.append(Case("forward", None, ("بصيرة",), forward=(chat, int(mid))))
    failures = 0
    for c in cases:
        if args.only and c.name not in args.only:
            continue
        last = await client.get_messages(args.bot, limit=1)
        after = last[0].id if last else 0
        t0 = time.monotonic()
        if c.image:
            await client.send_file(args.bot, c.image, force_document=False)
        elif c.name == "unsupported":
            await client.send_file(args.bot, __file__, force_document=True)
        elif c.forward:
            await client.forward_messages(args.bot, c.forward[1], c.forward[0])
        else:
            await client.send_message(args.bot, c.text or "")
        reply = await final_reply(client, args.bot, after)
        missing = [e for e in c.expect if e not in reply]
        present = [f for f in c.forbid if f in reply]
        ok = bool(reply) and not missing and not present
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {c.name:20} {time.monotonic() - t0:5.1f}s  chars={len(reply)}"
              + (f"  missing={missing}" if missing else "") + (f"  forbidden={present}" if present else ""))
        await asyncio.sleep(args.gap)
    await client.disconnect()
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("bot")
    p.add_argument("--image")
    p.add_argument("--forward-from", help="@channel:message_id of a public post quoting an ayah or hadith")
    p.add_argument("--only", nargs="*")
    p.add_argument("--gap", type=float, default=3.0, help="seconds between scenarios (stay under the rate limit)")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
