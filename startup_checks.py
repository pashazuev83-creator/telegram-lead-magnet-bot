"""Startup diagnostics.

Run once before polling starts:
  * getMe()               -> validates TELEGRAM_BOT_TOKEN
  * getChat(CHANNEL_ID)   -> validates CHANNEL_ID is reachable
  * getChatMember(bot)    -> validates the bot is an admin of the channel
  * PDF file existence    -> validates PDF_PATH

A bad token or an unreachable channel makes the bot useless for its single
job, so those are fatal (the process exits with a clear diagnostic instead
of a raw traceback). A missing PDF or missing admin rights are logged as
loud warnings but do NOT stop the process — they can be fixed while the bot
is already running (upload the PDF, promote the bot to admin) and the bot
will recover on the next check/request without a restart.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Settings, mask_token

logger = logging.getLogger("bot.startup")


class FatalStartupError(RuntimeError):
    """Raised for problems that make it pointless to start polling at all."""


async def check_bot_token(bot: Bot) -> str:
    """Call getMe(); return the bot's @username. Fatal on failure."""
    try:
        me = await bot.get_me()
    except TelegramAPIError as exc:
        raise FatalStartupError(
            "Не удалось авторизоваться в Telegram: TELEGRAM_BOT_TOKEN "
            "неверный или бот заблокирован. Проверь токен в .env."
        ) from exc
    logger.info("Токен валиден. Бот авторизован как @%s (id=%s)", me.username, me.id)
    return me.username or ""


async def check_channel_and_admin_rights(bot: Bot, settings: Settings) -> None:
    """Call getChat() then verify bot admin rights. Logs warnings, non-fatal."""
    try:
        chat = await bot.get_chat(settings.channel_id)
    except TelegramAPIError as exc:
        logger.error(
            "Не удалось получить канал CHANNEL_ID=%r: %s. "
            "Проверь, что канал существует и указан верно.",
            settings.channel_id_raw,
            exc,
        )
        return

    logger.info("Канал найден: %s (id=%s)", chat.title or chat.username, chat.id)

    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(settings.channel_id, me.id)
    except TelegramAPIError as exc:
        logger.error(
            "Не удалось проверить права бота в канале: %s. "
            "Скорее всего бот не добавлен в канал.",
            exc,
        )
        return

    if member.status not in ("administrator", "creator"):
        logger.warning(
            "Бот НЕ является администратором канала %s (статус: %s). "
            "Проверка подписки пользователей будет неуспешной, пока бота "
            "не добавят администратором (см. README).",
            settings.channel_id_raw,
            member.status,
        )
    else:
        logger.info("Бот является администратором канала — всё готово.")


def check_pdf_exists(settings: Settings) -> bool:
    """Return True if the PDF is present; log a clear error otherwise.

    Non-fatal: the bot keeps running so the operator can drop the file in
    place without restarting, but every delivery attempt will be refused
    with a friendly message until the file appears.
    """
    if settings.pdf_path.is_file():
        logger.info("PDF найден: %s", settings.pdf_path)
        return True

    logger.error(
        "PDF-файл не найден по пути %s (переменная PDF_PATH). "
        "Положи файл инструкции по этому пути — до этого бот не сможет "
        "выдавать материал пользователям.",
        settings.pdf_path,
    )
    return False


async def run_startup_checks(bot: Bot, settings: Settings) -> None:
    """Run all checks.

    Raises FatalStartupError for problems that make polling pointless (bad
    token). The caller (main()) is responsible for logging + a clean
    process exit, so it can close the bot's HTTP session first.
    """
    logger.info("Запуск диагностики перед стартом polling...")
    logger.info("Используется токен бота: %s", mask_token(settings.telegram_bot_token))

    username = await check_bot_token(bot)

    if settings.bot_username and username and settings.bot_username != username:
        logger.warning(
            "BOT_USERNAME в .env (%s) не совпадает с реальным username бота "
            "(@%s). Deep link в логах будет неверным — обнови BOT_USERNAME.",
            settings.bot_username,
            username,
        )

    await check_channel_and_admin_rights(bot, settings)
    check_pdf_exists(settings)

    logger.info("Диагностика завершена. Deep link для рекламы/Instagram:")
    logger.info(settings.deep_link)
