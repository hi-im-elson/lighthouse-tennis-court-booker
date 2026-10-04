import os
import sys
import argparse
from datetime import datetime, timedelta, time
import pytz
import yaml
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from dateutil.parser import parse as parse_date
import time as time_module

from utils.logger import log
from utils.notifications import send_notification
from utils.booker import get_reservation_url, create_browser_context, login_if_needed

load_dotenv()

USERNAME = os.environ.get("BL_USERNAME")
PASSWORD = os.environ.get("BL_PASSWORD")

PRIORITY_SLOTS = [
    ("18:00", "19:00", "6:00 PM - 7:00 PM"),
    ("17:00", "18:00", "5:00 PM - 6:00 PM"),
    ("19:00", "20:00", "7:00 PM - 8:00 PM"),
    ("16:00", "17:00", "4:00 PM - 5:00 PM"),
    ("11:00", "12:00", "11:00 AM - 12:00 PM"),
    ("10:00", "11:00", "10:00 AM - 11:00 AM"),
    ("15:00", "16:00", "3:00 PM - 4:00 PM"),
    ("14:00", "15:00", "2:00 PM - 3:00 PM"),
    ("12:00", "13:00", "12:00 PM - 1:00 PM"),
    ("13:00", "14:00", "1:00 PM - 2:00 PM"),
]


def load_config(profile: str) -> dict:
    with open("config.yml") as f:
        cfg = yaml.safe_load(f)
    if not cfg.get("enabled", True):
        log("Script disabled via config.yml. Exiting.", "WARNING")
        sys.exit(0)
    return cfg["profiles"][profile]


def parse_time_str(t_str: str) -> time:
    t_str = t_str.strip().upper()
    return datetime.strptime(t_str, "%I:%M %p" if ("AM" in t_str or "PM" in t_str) else "%H:%M").time()


def is_slot_in_range(slot_start: str, slot_end: str, range_str: str) -> bool:
    try:
        s_time = datetime.strptime(slot_start, "%H:%M").time()
        e_time = datetime.strptime(slot_end, "%H:%M").time()
        parts = [p.strip() for p in range_str.split("-")]
        if len(parts) != 2:
            return False
        return s_time >= parse_time_str(parts[0]) and e_time <= parse_time_str(parts[1])
    except Exception:
        return False


def save_page_html(page, target_date: str, label: str = "page"):
    try:
        os.makedirs("html", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"html/{label}_{target_date}_{timestamp}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(page.content())
        log(f"Saved HTML: {path}")
    except Exception as e:
        log(f"Failed to save HTML: {e}", "WARNING")


def set_target_date(tz="America/New York", days_offset=8):
    tz = pytz.timezone(tz)
    target_date = (datetime.now(tz) + timedelta(days=days_offset)).strftime("%Y-%m-%d") 
    return target_date


def book_court(profile: str = "court_booker"):
    cfg = load_config(profile)
    skip_booking = profile == "dry_run_no_save"
    headless = cfg["headless"]
    days_offset = cfg["days_offset"]
    save_html = cfg["save_html"]
    notifications = cfg["notifications"]

    log(f"=== {profile} started ===")

    if not USERNAME or not PASSWORD:
        log("Missing BL_USERNAME or BL_PASSWORD.", "ERROR")
        sys.exit(1)

    target_date = set_target_date(days_offset=8)
    next_target_date = set_target_date(days_offset=8) # placeholder value to be replaced
    url = get_reservation_url(target_date)
    log(f"Target date: {target_date} (+{days_offset}d), headless={headless}")

    with sync_playwright() as p:
        browser, context, page = create_browser_context(p, headless=headless)
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        log(f"Page loaded: {page.url}")

        login_if_needed(page, USERNAME, PASSWORD, log_fn=log)
        if save_html:
            save_page_html(page, target_date, label="after_login")

        deadline = time_module.time() + (60 if skip_booking else 240)
        retry_count = 0
        while True:

            if retry_count > 9 and target_date==next_target_date: # job inits at 23:59 for ~15 secs
                next_target_date = set_target_date(days_offset=7) # updates target date to one week from current date
                url = get_reservation_url(next_target_date)

            raw = page.url.split("selectedDate=")[-1] if "selectedDate=" in page.url else ""
            try:
                landed = parse_date(raw).strftime("%Y-%m-%d") if raw else ""
            except Exception:
                landed = raw

            if landed == target_date:
                log(f"Correct date confirmed: {landed}")
                break

            if skip_booking:
                log(f"[DRY RUN NO SAVE] Date mismatch (target={target_date}, landed={landed})", "WARNING")
                break

            if time_module.time() > deadline:
                msg = f"Redirect timeout. Target: {target_date}, Landed: {landed}"
                log(msg, "ERROR")
                send_notification("Tennis Court Booking Failed — Redirect Error", msg, enabled=notifications)
                browser.close()
                return

            retry_count += 1
            log(f"Date not ready (landed={landed}), retry #{retry_count} in 6s...", "DEBUG")
            time_module.sleep(6)
            page.goto(url, wait_until="domcontentloaded", timeout=15000)

        if page.query_selector("text=This Amenity is currently unavailable"):
            msg = f"Amenity unavailable on {target_date}."
            log(msg, "WARNING")
            if save_html:
                save_page_html(page, target_date, label="unavailable")
            send_notification("Tennis Court Booking Failed — Unavailable", msg, enabled=notifications)
            browser.close()
            return

        avail_table = None
        try:
            avail_table = page.wait_for_selector("#ctl00_ContentPlaceHolder1_AvailabileTimeSlotsList", timeout=5000)
        except Exception:
            pass

        if not avail_table:
            msg = f"Availability table not found for {target_date}."
            log(msg, "ERROR")
            if save_html:
                save_page_html(page, target_date, label="no_table")
            send_notification("Tennis Court Booking Failed — UI Element Missing", msg, enabled=notifications)
            browser.close()
            return

        td_elements = avail_table.query_selector_all("td")
        available_ranges = [td.inner_text().strip() for td in td_elements if td.inner_text().strip()]
        log(f"Available slots: {available_ranges}")
        if save_html:
            save_page_html(page, target_date, label="availability")

        if not available_ranges:
            msg = f"No available time slots on {target_date}."
            log(msg, "WARNING")
            send_notification("Tennis Court Booking Failed — No Slots Available", msg, enabled=notifications)
            browser.close()
            return

        selected_slot = next(
            (s for s in PRIORITY_SLOTS if any(is_slot_in_range(s[0], s[1], r) for r in available_ranges)),
            None,
        )

        if not selected_slot:
            msg = f"No preferred slot on {target_date}. Available: {', '.join(available_ranges)}"
            log(msg, "WARNING")
            send_notification("Tennis Court Booking Failed — Preferred Slots Taken", msg, enabled=notifications)
            browser.close()
            return

        s_start, s_end, label = selected_slot
        log(f"Selected slot: {label} ({s_start}–{s_end})")

        start_input = page.query_selector("#ctl00_ContentPlaceHolder1_StartTimePicker_dateInput")
        end_input = page.query_selector("#ctl00_ContentPlaceHolder1_EndTimePicker_dateInput")
        if start_input and end_input:
            start_input.fill(s_start)
            end_input.fill(s_end)
            page.keyboard.press("Tab")
            log("Time inputs filled.")
            if save_html:
                save_page_html(page, target_date, label="filled")

        if skip_booking:
            log(f"[DRY RUN NO SAVE] Would book '{label}' on {target_date}. Skipping save.")
        else:
            save_btn = page.query_selector(
                "#ctl00_ContentPlaceHolder1_FooterSaveButton, #ctl00_ContentPlaceHolder1_HeaderSaveButton"
            )
            if save_btn:
                save_btn.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                msg = f"Successfully booked tennis court for {target_date} at {label}."
                log(msg)
                send_notification("Tennis Court Booked Successfully!", msg, enabled=notifications)
            else:
                msg = f"Save button not found when booking {label} on {target_date}."
                log(msg, "ERROR")
                send_notification("Tennis Court Booking Failed — Save Button Missing", msg, enabled=notifications)

        browser.close()
        log(f"=== {profile} complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated tennis court booker.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run", action="store_true", help="Run in dry-run mode (headful, +7d, saves HTML, no booking)"
    )
    group.add_argument(
        "--dry-run-no-save", action="store_true", help="Dry run without saving HTML (for testing save logic)"
    )
    args = parser.parse_args()

    if args.dry_run:
        profile = "dry_run"
    elif args.dry_run_no_save:
        profile = "dry_run_no_save"
    else:
        profile = "court_booker"

    book_court(profile=profile)

