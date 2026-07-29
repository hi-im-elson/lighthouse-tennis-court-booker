"""
dry_run.py — DOM inspector for the BuildingLink booking page.
Run manually: python dry_run.py [--headless | --headful]
Prints availability table HTML and time picklist HTML. Never clicks Save.
"""

import os
import argparse
from typing import Optional
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

from utils.booker import get_reservation_url, create_browser_context, login_if_needed

load_dotenv()


def print_section(label: str, content: str):
    print(f"\n{'='*60}\n{label}\n{'='*60}\n{content}\n")


def run_dry_run(headless: bool = False, interactive: Optional[bool] = None):
    """
    Run DOM inspection for BuildingLink booking page.

    Args:
        headless: Whether to run the browser in headless mode.
        interactive: Whether to pause for user input before closing. Defaults to (not headless).
    """
    if interactive is None:
        interactive = not headless

    username = os.environ.get("BL_USERNAME")
    password = os.environ.get("BL_PASSWORD")

    if not username or not password:
        raise ValueError("Missing BL_USERNAME or BL_PASSWORD environment variables.")

    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    url = get_reservation_url(target_date)

    print(f"Target date: {target_date}")
    print(f"Navigating to URL: {url} (headless={headless})")

    with sync_playwright() as p:
        browser, context, page = create_browser_context(p, headless=headless)

        page.goto(url, wait_until="networkidle", timeout=15000)

        # Handle login redirect using shared helper
        login_if_needed(page, username, password, log_fn=print)

        landed_date = (
            page.url.split("selectedDate=")[-1] if "selectedDate=" in page.url else "unknown"
        )
        print_section(
            "LANDED DATE (confirm matches target)",
            f"Target: {target_date}\nLanded: {landed_date}",
        )

        print_section("PAGE TITLE", page.title())

        # Availability table
        avail_table = page.query_selector("#ctl00_ContentPlaceHolder1_AvailabileTimeSlotsList")
        print_section(
            "AVAILABILITY TABLE HTML",
            avail_table.inner_html() if avail_table else "NOT FOUND — selector may have changed",
        )

        # All <td> text content so we can confirm parsing targets
        if avail_table:
            tds = avail_table.query_selector_all("td")
            td_texts = [td.inner_text().strip() for td in tds if td.inner_text().strip()]
            print_section(
                "AVAILABILITY TD TEXT VALUES",
                "\n".join(td_texts) if td_texts else "No populated <td> found",
            )

        # Unavailability message
        unavail = page.query_selector("text=This Amenity is currently unavailable")
        print_section("UNAVAILABLE MESSAGE", unavail.inner_text() if unavail else "Not present")

        # Start time picklist candidate elements
        start_candidates = [
            "select[id*='start' i]",
            "input[id*='start' i]",
            "[id*='StartTime']",
            "[id*='start_time']",
            "[class*='start' i]",
            "[id*='From']",
        ]
        print_section("START TIME — CANDIDATE ELEMENTS", "")
        for sel in start_candidates:
            els = page.query_selector_all(sel)
            for el in els:
                print(f"  Selector: {sel}")
                print(f"  Tag:      {el.evaluate('el => el.tagName')}")
                print(f"  ID:       {el.get_attribute('id')}")
                print(f"  Class:    {el.get_attribute('class')}")
                print(f"  HTML:     {el.evaluate('el => el.outerHTML')[:500]}")
                print()

        # End time picklist candidate elements
        end_candidates = [
            "select[id*='end' i]",
            "input[id*='end' i]",
            "[id*='EndTime']",
            "[id*='end_time']",
            "[class*='end' i]",
            "[id*='To']",
        ]
        print_section("END TIME — CANDIDATE ELEMENTS", "")
        for sel in end_candidates:
            els = page.query_selector_all(sel)
            for el in els:
                print(f"  Selector: {sel}")
                print(f"  Tag:      {el.evaluate('el => el.tagName')}")
                print(f"  ID:       {el.get_attribute('id')}")
                print(f"  Class:    {el.get_attribute('class')}")
                print(f"  HTML:     {el.evaluate('el => el.outerHTML')[:500]}")
                print()

        # Save button element
        save_btn = page.query_selector(
            "#ctl00_ContentPlaceHolder1_FooterSaveButton, #ctl00_ContentPlaceHolder1_HeaderSaveButton"
        )
        print_section(
            "SAVE BUTTON ELEMENT",
            save_btn.evaluate("el => el.outerHTML")[:300]
            if save_btn
            else "NOT FOUND — selector may have changed",
        )

        # Dump full page HTML as a fallback
        print_section("FULL PAGE HTML (truncated to 8000 chars)", page.content()[:8000])

        if interactive:
            input(
                "\nInspection complete. Browser is still open — check it visually if needed. Press Enter to close."
            )

        browser.close()


if __name__ == "__main__":
    from typing import Optional

    parser = argparse.ArgumentParser(
        description="DOM inspector for BuildingLink booking page."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode (no GUI)"
    )
    group.add_argument(
        "--headful", action="store_true", help="Run browser in headful mode (visible GUI)"
    )

    args = parser.parse_args()

    # Default to headful (headless=False) for dry_run unless --headless is explicitly passed
    is_headless = True if args.headless else False
    run_dry_run(headless=is_headless)
