"""Inline keyboards used by the bot."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from texts import BTN_CHECK, BTN_SUBSCRIBE, CALLBACK_CHECK_SUBSCRIPTION


def get_subscribe_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    """Two-button keyboard: 'Subscribe' (URL) + 'Check subscription' (callback)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SUBSCRIBE, url=channel_url)],
            [
                InlineKeyboardButton(
                    text=BTN_CHECK, callback_data=CALLBACK_CHECK_SUBSCRIPTION
                )
            ],
        ]
    )
