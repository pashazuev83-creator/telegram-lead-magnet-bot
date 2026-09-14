#!/usr/bin/env python3
"""Entry point: Telegram lead-magnet bot.

Flow: Start -> Subscribe -> Check subscription -> PDF.

Local dev:  long polling, python bot.py
Production: same long polling, run in Docker on any always-on host
            (Railway worker, Render worker, a VPS, etc). No webhook/domain
            needed for this version.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import ConfigError, load_settings
from handlers import setup_handlers
from startup_checks import FatalStartupError, run_startup_checks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot.main")


async def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.critical("Ошибка конфигурации: %s", exc)
        sys.exit(1)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(setup_handlers(settings))

    try:
        await run_startup_checks(bot, settings)
    except FatalStartupError as exc:
        logger.critical(str(exc))
        await bot.session.close()
        sys.exit(1)

    logger.info("Запускаю long polling...")
    # handle_signals=True (default) installs SIGINT/SIGTERM handlers, and
    # close_bot_session=True (default) closes the HTTP session on shutdown —
    # together this gives a clean exit on Ctrl+C / `docker stop` without any
    # extra code here.
    await dp.start_polling(bot)
    logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C.")
