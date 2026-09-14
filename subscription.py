"""Pure logic for deciding whether a chat member counts as "subscribed".

Kept separate from the handlers so it can be unit-tested without touching
the Telegram API at all.
"""

from __future__ import annotations

from aiogram.types import ChatMemberUnion

_SUBSCRIBED_STATUSES = {"creator", "administrator", "member"}


def is_subscribed(member: ChatMemberUnion) -> bool:
    """True if this chat member should be treated as subscribed.

    Rules (per spec):
      * creator / administrator / member -> subscribed
      * restricted -> subscribed only if ``is_member`` is True
      * left / kicked (banned) / anything else -> not subscribed
    """
    status = member.status
    if status in _SUBSCRIBED_STATUSES:
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False
