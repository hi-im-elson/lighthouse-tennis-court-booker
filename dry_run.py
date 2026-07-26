"""
dry_run.py — DOM inspector for the BuildingLink booking page.
Run manually: python dry_run.py
Prints availability table HTML and time picklist HTML. Never clicks Save.
"""

import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.environ["BL_USERNAME"]
PASSWORD = os.environ["BL_PASSWORD"]

TARGET_DATE = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")
URL = f"https://lighthousewest-tscc2794.buildinglink.com/V2/Tenant/Amenities/NewReservation.aspx?amenityId=68068&from=0&selectedDate={TARGET_DATE}"


def print_section(label: str, content: str):
    print(f"\n{'='*60}\n{label}\n{'='*60}\n{content}\n")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headful so you can watch
    page = browser.new_page()

    page.goto(URL, wait_until="networkidle", timeout=15000)

    # Handle login redirect
    if "Login" in page.title() or "login" in page.url.lower():
        page.fill("input[name*='user' i], input[type='text']", USERNAME)
        page.fill("input[name*='pass' i], input[type='password']", PASSWORD)
        page.click("input[type='submit'], button[type='submit']")
        page.wait_for_load_state("networkidle", timeout=15000)

    landed_date = page.url.split("selectedDate=")[-1] if "selectedDate=" in page.url else "unknown"
    print_section("LANDED DATE (confirm matches target)", f"Target: {TARGET_DATE}\nLanded: {landed_date}")

    print_section("PAGE TITLE", page.title())

    # Availability table
    avail_table = page.query_selector("#ctl00_ContentPlaceHolder1_AvailabileTimeSlotsList")
    print_section(
        "AVAILABILITY TABLE HTML",
        avail_table.inner_html() if avail_table else "NOT FOUND — selector may have changed"
    )

    # All <td> text content so we can confirm parsing targets
    if avail_table:
        tds = avail_table.query_selector_all("td")
        td_texts = [td.inner_text().strip() for td in tds if td.inner_text().strip()]
        print_section("AVAILABILITY TD TEXT VALUES", "\n".join(td_texts) if td_texts else "No populated <td> found")

    # Unavailability message
    unavail = page.query_selector("text=This Amenity is currently unavailable")
    print_section("UNAVAILABLE MESSAGE", unavail.inner_text() if unavail else "Not present")

    # Start time picklist — cast a wide net on likely selectors
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

    # End time picklist
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

    # Save button
    save_candidates = ["input[value*='Save' i]", "button[id*='save' i]", "input[id*='save' i]", "button:has-text('Save')"]
    print_section("SAVE BUTTON — CANDIDATE ELEMENTS", "")
    for sel in save_candidates:
        el = page.query_selector(sel)
        if el:
            print(f"  Selector: {sel}")
            print(f"  HTML:     {el.evaluate('el => el.outerHTML')[:300]}")
            print()

    # Dump full page HTML as a fallback if all selectors miss
    print_section("FULL PAGE HTML (truncated to 8000 chars)", page.content()[:8000])

    input("\nInspection complete. Browser is still open — check it visually if needed. Press Enter to close.")
    browser.close()
