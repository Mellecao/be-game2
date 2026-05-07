import time

import pytest


def test_acquire_returns_context():
    from server.playwright_helper import acquire_browser
    ctx = acquire_browser()
    assert ctx is not None
    assert hasattr(ctx, "new_page")


def test_rate_limit_at_least_one_second_between_calls(monkeypatch):
    from server import playwright_helper

    calls = []
    def fake_sleep(s):
        calls.append(s)

    monkeypatch.setattr(playwright_helper.time, "sleep", fake_sleep)
    playwright_helper._last_request_ts = time.time()
    playwright_helper.respect_rate_limit()
    assert calls and calls[0] >= 0.9
