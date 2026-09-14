"""Startup diagnostics tests (scenarios 7, 8, 9 at process-start time)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.methods import GetChat, GetMe

from config import Settings
from startup_checks import (
    FatalStartupError,
    check_bot_token,
    check_pdf_exists,
    run_startup_checks,
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        telegram_bot_token="123456:TEST",
        channel_id="@test_channel",
        channel_id_raw="@test_channel",
        channel_url="https://t.me/test_channel",
        pdf_path=tmp_path / "guide.pdf",
        bot_username="test_bot",
    )


@pytest.mark.asyncio
async def test_check_bot_token_ok():
    bot = MagicMock()
    bot.get_me = AsyncMock(return_value=SimpleNamespace(username="test_bot", id=1))
    username = await check_bot_token(bot)
    assert username == "test_bot"


@pytest.mark.asyncio
async def test_check_bot_token_invalid_raises_fatal():
    bot = MagicMock()
    bot.get_me = AsyncMock(
        side_effect=TelegramUnauthorizedError(method=GetMe(), message="Unauthorized")
    )
    with pytest.raises(FatalStartupError):
        await check_bot_token(bot)


def test_check_pdf_exists_false_when_missing(settings):
    assert check_pdf_exists(settings) is False


def test_check_pdf_exists_true_when_present(settings):
    settings.pdf_path.write_bytes(b"%PDF-1.4")
    assert check_pdf_exists(settings) is True


@pytest.mark.asyncio
async def test_run_startup_checks_raises_fatal_on_bad_token(settings):
    bot = MagicMock()
    bot.get_me = AsyncMock(
        side_effect=TelegramUnauthorizedError(method=GetMe(), message="Unauthorized")
    )
    with pytest.raises(FatalStartupError):
        await run_startup_checks(bot, settings)


@pytest.mark.asyncio
async def test_run_startup_checks_survives_missing_pdf_and_bad_channel(settings):
    """A bad CHANNEL_ID / missing PDF must not crash the process — the bot
    should still come up so it can be fixed without a restart."""
    bot = MagicMock()
    bot.get_me = AsyncMock(return_value=SimpleNamespace(username="test_bot", id=1))
    chat_error = TelegramAPIError(method=GetChat(chat_id="@missing"), message="chat not found")
    bot.get_chat = AsyncMock(side_effect=chat_error)
    bot.get_chat_member = AsyncMock(side_effect=chat_error)

    # Should complete without raising.
    await run_startup_checks(bot, settings)
