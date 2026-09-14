"""Ensures the bot only reacts in private chats (spec: never in groups)."""

from types import SimpleNamespace

import pytest
from aiogram import F


@pytest.mark.parametrize(
    ("chat_type", "expected"),
    [
        ("private", True),
        ("group", False),
        ("supergroup", False),
        ("channel", False),
    ],
)
def test_message_chat_type_filter(chat_type, expected):
    message = SimpleNamespace(chat=SimpleNamespace(type=chat_type))
    magic_filter = F.chat.type == "private"
    assert bool(magic_filter.resolve(message)) is expected


@pytest.mark.parametrize(
    ("chat_type", "expected"),
    [("private", True), ("group", False)],
)
def test_callback_message_chat_type_filter(chat_type, expected):
    callback = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(type=chat_type)))
    magic_filter = F.message.chat.type == "private"
    assert bool(magic_filter.resolve(callback)) is expected
