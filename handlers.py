"""Telegram update handlers: /start and the subscription-check callback.

The whole flow is intentionally tiny: Start -> Subscribe -> Check -> PDF.

The actual logic lives in ``process_start`` / ``process_check_subscription``
(plain async functions, not decorator closures) so it can be unit-tested
directly with mocked aiogram objects, without spinning up a Dispatcher.
``setup_handlers`` just wires those functions to a Router.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InaccessibleMessage, Message

from config import Settings
from keyboards import get_subscribe_keyboard
from subscription import is_subscribed
from texts import (
    CALLBACK_CHECK_SUBSCRIPTION,
    CHECK_FAILED_TEXT,
    NOT_SUBSCRIBED_TEXT,
    PDF_CAPTION,
    PDF_UNAVAILABLE_TEXT,
    SUBSCRIBED_TEXT,
    THROTTLED_ALERT_TEXT,
    WELCOME_TEXT,
)
from throttling import SimpleThrottler

logger = logging.getLogger("bot.handlers")

# One click per user per this many seconds is enough for a human; anything
# faster is a double-tap / spam and gets silently swallowed (after we still
# answer the callback so Telegram's loading spinner stops).
CHECK_THROTTLE_SECONDS = 2.0


async def process_start(message: Message, command: CommandObject, settings: Settings) -> None:
    user = message.from_user
    deep_link_arg = command.args
    logger.info(
        "/start от user_id=%s username=%s deep_link_arg=%r",
        user.id if user else None,
        user.username if user else None,
        deep_link_arg,
    )
    await message.answer(
        WELCOME_TEXT,
        reply_markup=get_subscribe_keyboard(settings.channel_url),
    )


async def process_check_subscription(
    callback: CallbackQuery,
    settings: Settings,
    check_throttler: SimpleThrottler,
) -> None:
    user = callback.from_user
    user_id = user.id  # trusted source: the real Telegram user who tapped
    # the button, never anything derived from callback_data or user text.

    bot = callback.bot
    message = callback.message
    if bot is None or message is None or isinstance(message, InaccessibleMessage):
        # Defensive: shouldn't happen given the router's chat-type filter,
        # but the aiogram types allow it (e.g. a very old/edited message).
        logger.warning(
            "callback без доступного bot/message (user_id=%s) — пропускаем", user_id
        )
        await callback.answer()
        return

    if not check_throttler.allow(user_id):
        await callback.answer(THROTTLED_ALERT_TEXT)
        return

    logger.info("Проверка подписки: user_id=%s username=%s", user_id, user.username)

    try:
        member = await bot.get_chat_member(settings.channel_id, user_id)
    except TelegramAPIError as exc:
        logger.error(
            "Ошибка Telegram API при проверке подписки (user_id=%s): %s",
            user_id,
            exc,
        )
        await callback.answer()
        await message.answer(CHECK_FAILED_TEXT)
        return
    except Exception:  # noqa: BLE001 - defensive: never crash a handler
        logger.exception(
            "Непредвиденная ошибка при проверке подписки (user_id=%s)", user_id
        )
        await callback.answer()
        await message.answer(CHECK_FAILED_TEXT)
        return

    if not is_subscribed(member):
        logger.info("user_id=%s НЕ подписан (статус=%s)", user_id, member.status)
        await callback.answer()
        await message.answer(
            NOT_SUBSCRIBED_TEXT,
            reply_markup=get_subscribe_keyboard(settings.channel_url),
        )
        return

    logger.info("user_id=%s подписан (статус=%s) — выдаём PDF", user_id, member.status)
    await callback.answer()
    await message.answer(SUBSCRIBED_TEXT)

    if not settings.pdf_path.is_file():
        logger.error(
            "PDF не найден по пути %s в момент выдачи (user_id=%s)",
            settings.pdf_path,
            user_id,
        )
        await message.answer(PDF_UNAVAILABLE_TEXT)
        return

    try:
        await message.answer_document(
            FSInputFile(settings.pdf_path),
            caption=PDF_CAPTION,
        )
    except TelegramAPIError as exc:
        logger.error("Не удалось отправить PDF (user_id=%s): %s", user_id, exc)
        await message.answer(PDF_UNAVAILABLE_TEXT)


def setup_handlers(settings: Settings, throttler: SimpleThrottler | None = None) -> Router:
    """Build a fresh router bound to the given Settings.

    Settings (and optionally a throttler, for tests) are injected rather
    than imported as module-level singletons, so this can be re-created
    with a temporary configuration in tests.
    """
    router = Router(name="lead_magnet")
    check_throttler = throttler or SimpleThrottler(ttl_seconds=CHECK_THROTTLE_SECONDS)

    @router.message(CommandStart(), F.chat.type == "private")
    async def _on_start(message: Message, command: CommandObject) -> None:
        await process_start(message, command, settings)

    @router.callback_query(
        F.data == CALLBACK_CHECK_SUBSCRIPTION,
        F.message.chat.type == "private",
    )
    async def _on_check_subscription(callback: CallbackQuery) -> None:
        await process_check_subscription(callback, settings, check_throttler)

    return router
