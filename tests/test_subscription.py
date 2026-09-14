"""Scenario coverage for the subscribed/not-subscribed decision (pure logic,
no network — corresponds to scenarios 2-6 from the spec's test plan)."""

from types import SimpleNamespace

import pytest

from subscription import is_subscribed


def member(status: str, **extra):
    return SimpleNamespace(status=status, **extra)


@pytest.mark.parametrize("status", ["creator", "administrator", "member"])
def test_subscribed_statuses(status):
    assert is_subscribed(member(status)) is True


def test_restricted_but_still_member():
    assert is_subscribed(member("restricted", is_member=True)) is True


def test_restricted_and_not_member():
    assert is_subscribed(member("restricted", is_member=False)) is False


def test_restricted_missing_is_member_field_defaults_false():
    assert is_subscribed(member("restricted")) is False


@pytest.mark.parametrize("status", ["left", "kicked"])
def test_not_subscribed_statuses(status):
    assert is_subscribed(member(status)) is False
