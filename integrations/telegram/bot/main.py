"""Entry point: ``python -m bot.main``. Long polling by default; webhook when TELEGRAM_WEBHOOK_URL is set (E-059)."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from bot.client import BasiraClient, BasiraError
from bot.config import ConfigError, Settings
from bot.handlers import BasiraBot

log = logging.getLogger("basira.bot")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout
    )
    # httpx logs full request URLs at INFO — those contain the bot token. Keep them out of every log.
    for noisy in ("httpx", "httpcore", "telegram.ext.Updater", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def build(settings: Settings) -> tuple[Application[Any, Any, Any, Any, Any, Any], BasiraClient]:
    client = BasiraClient(
        settings.api_url,
        eval_key=settings.eval_key,
        text_timeout=settings.text_timeout,
        image_timeout=settings.image_timeout,
    )
    app = (
        ApplicationBuilder()
        .token(settings.token)
        .concurrent_updates(16)
        .connect_timeout(10)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    BasiraBot(settings, client).register(app)
    beat = Path(settings.heartbeat_file)
    tasks: set[asyncio.Task[None]] = set()

    async def heartbeat() -> None:  # liveness for the container HEALTHCHECK: a timestamp, nothing else
        while True:
            beat.write_text(str(int(time.time())))
            await asyncio.sleep(30)

    async def post_init(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        try:
            h = await client.health()
            log.info("basira_api=up build=%s corpus_loaded=%s", h.get("build_sha"), h.get("corpus_loaded"))
            await client.messages("ar")
        except BasiraError as e:  # the bot still starts; every reply reports the outage honestly
            log.warning("basira_api=unreachable error=%s", type(e).__name__)
        me = await application.bot.get_me()
        log.info("bot=@%s mode=%s", me.username, "webhook" if settings.webhook_url else "polling")
        t = asyncio.create_task(heartbeat())
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    async def post_shutdown(_: Application[Any, Any, Any, Any, Any, Any]) -> None:
        for t in tasks:
            t.cancel()
        await client.aclose()

    app.post_init = post_init
    app.post_shutdown = post_shutdown
    return app, client


def main() -> int:
    _configure_logging()
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        log.error("config_error %s", e)
        return 2
    app, _ = build(settings)
    allowed = [Update.MESSAGE]
    if settings.webhook_url:
        app.run_webhook(
            listen="0.0.0.0",  # inside the container; the proxy terminates TLS
            port=settings.port,
            url_path="telegram",
            webhook_url=f"{settings.webhook_url.rstrip('/')}/telegram",
            secret_token=settings.webhook_secret,
            allowed_updates=allowed,
            drop_pending_updates=False,
        )
    else:
        app.run_polling(allowed_updates=allowed, drop_pending_updates=False)
    return 0


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    raise SystemExit(main())
