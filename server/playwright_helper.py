"""Singleton Playwright browser context, stealth-enabled, rate-limited."""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_browser = None
_context = None
_playwright = None
_last_request_ts: float = 0.0
_rate_lock = threading.Lock()
RATE_LIMIT_SEC = 1.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def acquire_browser():
    """Returns a shared browser context. Lazy-initializes on first call."""
    global _browser, _context, _playwright
    with _lock:
        if _context is not None:
            return _context

        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = _browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )

        # Apply stealth - handle both v1 and v2 APIs of playwright-stealth.
        # v1: from playwright_stealth import stealth_sync; stealth_sync(page)
        # v2: from playwright_stealth import Stealth; Stealth().apply_stealth_sync(page) or similar
        # Wrap in try/except - stealth is best-effort, not critical.
        try:
            from playwright_stealth import Stealth  # v2
            stealth = Stealth()
            page = _context.new_page()
            # v2 may expose apply_stealth_sync, apply_stealth, or apply on the Stealth() instance
            if hasattr(stealth, "apply_stealth_sync"):
                stealth.apply_stealth_sync(page)
            elif hasattr(stealth, "apply"):
                stealth.apply(page)
            page.close()
        except ImportError:
            try:
                from playwright_stealth import stealth_sync  # v1 fallback
                page = _context.new_page()
                stealth_sync(page)
                page.close()
            except Exception:
                pass
        except Exception:
            pass

        return _context


def respect_rate_limit() -> None:
    """Garante >= RATE_LIMIT_SEC entre requests."""
    global _last_request_ts
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_ts
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        _last_request_ts = time.time()


def shutdown() -> None:
    """Cleanup global. Chamado em atexit."""
    global _browser, _context, _playwright
    with _lock:
        try:
            if _context: _context.close()
            if _browser: _browser.close()
            if _playwright: _playwright.stop()
        except Exception:
            pass
        _browser = _context = _playwright = None


import atexit
atexit.register(shutdown)
