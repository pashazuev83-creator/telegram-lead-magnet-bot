import pytest

from config import ConfigError, parse_channel_id


def test_parse_channel_id_at_username():
    assert parse_channel_id("@my_channel") == "@my_channel"


def test_parse_channel_id_numeric_negative():
    assert parse_channel_id("-1001234567890") == -1001234567890


def test_parse_channel_id_numeric_positive():
    assert parse_channel_id("12345") == 12345


def test_parse_channel_id_bare_username_gets_at_prefix():
    assert parse_channel_id("my_channel") == "@my_channel"


def test_parse_channel_id_empty_raises():
    with pytest.raises(ConfigError):
        parse_channel_id("   ")
