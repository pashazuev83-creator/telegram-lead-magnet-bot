from throttling import SimpleThrottler


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_first_call_always_allowed():
    throttler = SimpleThrottler(ttl_seconds=2.0, clock=FakeClock())
    assert throttler.allow(1) is True


def test_rapid_repeat_click_is_blocked():
    clock = FakeClock()
    throttler = SimpleThrottler(ttl_seconds=2.0, clock=clock)
    assert throttler.allow(1) is True
    clock.advance(0.1)
    assert throttler.allow(1) is False  # scenario 10: rapid repeated clicks


def test_call_after_ttl_expires_is_allowed_again():
    clock = FakeClock()
    throttler = SimpleThrottler(ttl_seconds=2.0, clock=clock)
    assert throttler.allow(1) is True
    clock.advance(2.1)
    assert throttler.allow(1) is True


def test_different_users_do_not_block_each_other():
    clock = FakeClock()
    throttler = SimpleThrottler(ttl_seconds=2.0, clock=clock)
    assert throttler.allow(1) is True
    assert throttler.allow(2) is True
