"""
utils/booker.py — Shared automation utilities for BuildingLink court booking.
"""

from typing import Tuple, Callable, Optional
from playwright.sync_api import Playwright, Browser, BrowserContext, Page


BUILDINGLINK_BASE_URL = (
    "https://lighthousewest-tscc2794.buildinglink.com/V2/Tenant/Amenities/NewReservation.aspx"
)


def get_reservation_url(target_date: str) -> str:
    """Generate BuildingLink new reservation URL for a given target date string (YYYY-MM-DD)."""
    return f"{BUILDINGLINK_BASE_URL}?amenityId=68068&from=0&selectedDate={target_date}"


def create_browser_context(
    playwright: Playwright, headless: bool = True
) -> Tuple[Browser, BrowserContext, Page]:
    """Launch Chromium browser and return browser, context, and new page."""
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    return browser, context, page


def login_if_needed(
    page: Page,
    username: str,
    password: str,
    log_fn: Optional[Callable[[str], None]] = None,
):
    """Detect login redirect and submit user credentials if required."""
    is_login_page = "login" in page.url.lower() or "login" in (page.title() or "").lower()
    if is_login_page:
        if log_fn:
            log_fn("Login redirect detected. Attempting authentication.")
        page.fill("#Username, input[name*='user' i]", username)
        page.fill("#Password, input[type='password']", password)
        login_btn = page.query_selector(
            "#LoginButton, input[type='image'], input[type='submit'], button[type='submit']"
        )
        if login_btn and login_btn.is_visible():
            login_btn.click()
        else:
            page.keyboard.press("Enter")

        page.wait_for_url(lambda u: "login" not in u.lower(), timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        if log_fn:
            log_fn("Login successful.")
