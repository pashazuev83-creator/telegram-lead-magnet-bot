"""Higher-level tests for the handler logic, with the Telegram Bot API
mocked out (AsyncMock). No real network / real bot token involved.

Scenario numbers refer to the manual test plan in the task/README:
  1  new user /start
  2  not subscribed -> Check -> no PDF
  3  user subscribes
  4  Check again -> gets PDF
  5  already-subscribed user gets PDF right away on Check
  6  user unsubscribed -> Check no longer gives the file
  7  wrong CHANNEL_ID -> generic error, no crash
  8  wrong bot token -> covered by startup_checks (see test_startup_checks.py)
  9  missing PDF -> generic error, no crash
  10 rapid repeated clicks -> throttled (see test_throttling.py + this file)
  11 /start with ?start=guide deep-link arg
  12 plain /start
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember

from config import Settings
from handlers import process_check_subscription, process_start
from tests.test_subscription import member
from texts import (
    CHECK_FAILED_TEXT,
    NOT_SUBSCRIBED_TEXT,
    PDF_CAPTION,
    PDF_UNAVAILABLE_TEXT,
    SUBSCRIBED_TEXT,
    WELCOME_TEXT,
)
from throttling import SimpleThrottler


@pytest.fixture
def settings(tmp_path) -> Settings:
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return Settings(
        telegram_bot_token="123456:TEST",
        channel_id="@test_channel",
        channel_id_raw="@test_channel",
        channel_url="https://t.me/test_channel",
        pdf_path=pdf,
        bot_username="test_bot",
    )


def make_callback(user_id: int = 42, username: str = "pavel"):
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=user_id, username=username)
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()
    callback.message.answer_document = AsyncMock()
    callback.bot = MagicMock()
    callback.bot.get_chat_member = AsyncMock()
    return callback


def make_message():
    message = MagicMock()
    message.from_user = SimpleNamespace(id=42, username="pavel")
    message.answer = AsyncMock()
    return message


# ---- /start (scenarios 1, 11, 12) ----------------------------------------


@pytest.mark.asyncio
async def test_start_plain(settings):
    message = make_message()
    command = SimpleNamespace(args=None)
    await process_start(message, command, settings)
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert text == WELCOME_TEXT
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].url == settings.channel_url


@pytest.mark.asyncio
async def test_start_with_deep_link_guide(settings):
    message = make_message()
    command = SimpleNamespace(args="guide")
    await process_start(message, command, settings)
    message.answer.assert_awaited_once()


# ---- check subscription: not subscribed (scenario 2) ----------------------


@pytest.mark.asyncio
async def test_check_not_subscribed_no_pdf(settings):
    callback = make_callback()
    callback.bot.get_chat_member.return_value = member("left")
    throttler = SimpleThrottler(ttl_seconds=0)  # disabled for this test

    await process_check_subscription(callback, settings, throttler)

    args, kwargs = callback.message.answer.await_args
    assert args[0] == NOT_SUBSCRIBED_TEXT
    assert "reply_markup" in kwargs
    callback.message.answer_document.assert_not_awaited()
    callback.answer.assert_awaited()


# ---- check subscription: subscribed -> PDF (scenarios 3, 4, 5) -----------


@pytest.mark.asyncio
async def test_check_subscribed_sends_pdf(settings):
    callback = make_callback()
    callback.bot.get_chat_member.return_value = member("member")
    throttler = SimpleThrottler(ttl_seconds=0)

    await process_check_subscription(callback, settings, throttler)

    # First call: success text.
    first_call_args = callback.message.answer.await_args_list[0].args
    assert first_call_args[0] == SUBSCRIBED_TEXT

    callback.message.answer_document.assert_awaited_once()
    _, kwargs = callback.message.answer_document.await_args
    assert kwargs["caption"] == PDF_CAPTION


@pytest.mark.asyncio
async def test_already_subscribed_gets_pdf_immediately(settings):
    """Scenario 5: an already-subscribed user hits Check once and gets the
    file right away (no separate 'subscribe first' step needed)."""
    callback = make_callback()
    callback.bot.get_chat_member.return_value = member("creator")
    throttler = SimpleThrottler(ttl_seconds=0)

    await process_check_subscription(callback, settings, throttler)

    callback.message.answer_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_unsubscribes_after_getting_pdf(settings):
    """Scenario 6: user had access, then left the channel -> next Check
    does not deliver the file again."""
    callback = make_callback()
    throttler = SimpleThrottler(ttl_seconds=0)

    callback.bot.get_chat_member.return_value = member("member")
    await process_check_subscription(callback, settings, throttler)
    callback.message.answer_document.assert_awaited_once()

    callback.bot.get_chat_member.return_value = member("left")
    await process_check_subscription(callback, settings, throttler)
    # Still only the one call from before -> no new document sent.
    callback.message.answer_document.assert_awaited_once()


# ---- Telegram API errors (scenario 7: bad CHANNEL_ID / API failure) ------


@pytest.mark.asyncio
async def test_api_error_shows_generic_message_and_does_not_crash(settings):
    callback = make_callback()
    callback.bot.get_chat_member.side_effect = TelegramBadRequest(
        method=GetChatMember(chat_id="@test_channel", user_id=42),
        message="Bad Request: chat not found",
    )
    throttler = SimpleThrottler(ttl_seconds=0)

    await process_check_subscription(callback, settings, throttler)

    args, _ = callback.message.answer.await_args
    assert args[0] == CHECK_FAILED_TEXT
    callback.message.answer_document.assert_not_awaited()
    callback.answer.assert_awaited()  # spinner must always stop


@pytest.mark.asyncio
async def test_unexpected_exception_is_contained(settings):
    callback = make_callback()
    callback.bot.get_chat_member.side_effect = RuntimeError("boom")
    throttler = SimpleThrottler(ttl_seconds=0)

    # Must not raise.
    await process_check_subscription(callback, settings, throttler)

    args, _ = callback.message.answer.await_args
    assert args[0] == CHECK_FAILED_TEXT


# ---- missing PDF (scenario 9) ---------------------------------------------


@pytest.mark.asyncio
async def test_missing_pdf_does_not_crash(settings, tmp_path):
    settings.pdf_path.unlink()  # simulate PDF removed/never uploaded
    callback = make_callback()
    callback.bot.get_chat_member.return_value = member("member")
    throttler = SimpleThrottler(ttl_seconds=0)

    await process_check_subscription(callback, settings, throttler)

    callback.message.answer_document.assert_not_awaited()
    last_text = callback.message.answer.await_args_list[-1].args[0]
    assert last_text == PDF_UNAVAILABLE_TEXT


# ---- throttling inside the real handler path (scenario 10) ---------------


@pytest.mark.asyncio
async def test_rapid_double_click_only_checks_api_once(settings):
    callback = make_callback()
    callback.bot.get_chat_member.return_value = member("member")
    throttler = SimpleThrottler(ttl_seconds=999)  # never expires in this test

    await process_check_subscription(callback, settings, throttler)
    await process_check_subscription(callback, settings, throttler)

    callback.bot.get_chat_member.assert_awaited_once()
    callback.message.answer_document.assert_awaited_once()
    # callback.answer must still be called both times so the spinner stops.
    assert callback.answer.await_count == 2


@pytest.mark.asyncio
async def test_different_users_are_not_cross_throttled(settings):
    throttler = SimpleThrottler(ttl_seconds=999)

    callback_a = make_callback(user_id=1)
    callback_a.bot.get_chat_member.return_value = member("member")
    callback_b = make_callback(user_id=2)
    callback_b.bot.get_chat_member.return_value = member("member")

    await process_check_subscription(callback_a, settings, throttler)
    await process_check_subscription(callback_b, settings, throttler)

    callback_a.bot.get_chat_member.assert_awaited_once()
    callback_b.bot.get_chat_member.assert_awaited_once()


# ---- user_id must come from the real caller, never from callback_data ----


@pytest.mark.asyncio
async def test_uses_real_from_user_id_not_arbitrary_input(settings):
    callback = make_callback(user_id=999)
    callback.bot.get_chat_member.return_value = member("member")
    throttler = SimpleThrottler(ttl_seconds=0)

    await process_check_subscription(callback, settings, throttler)

    call_args = callback.bot.get_chat_member.await_args
    assert call_args.args[1] == 999 or call_args.kwargs.get("user_id") == 999
