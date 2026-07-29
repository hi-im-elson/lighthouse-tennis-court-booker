import os
import sys
import smtplib
import argparse
from email.message import EmailMessage
from datetime import datetime, timedelta, time
import pytz
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from dateutil.parser import parse as parse_date
import time as time_module

from logger import log
from utils.booker import get_reservation_url, create_browser_context, login_if_needed

load_dotenv()

USERNAME = os.environ.get("BL_USERNAME")
PASSWORD = os.environ.get("BL_PASSWORD")
NOTIFY_TO = os.environ.get("NOTIFY_EMAIL_TO")
NOTIFY_FROM = os.environ.get("NOTIFY_EMAIL_FROM")
NOTIFY_PASS = os.environ.get("NOTIFY_EMAIL_PASSWORD")

PRIORITY_SLOTS = [
    ("18:00", "19:00", "6:00 PM - 7:00 PM"),
    ("19:00", "20:00", "7:00 PM - 8:00 PM"),
    ("17:00", "18:00", "5:00 PM - 6:00 PM"),
    ("16:00", "17:00", "4:00 PM - 5:00 PM"),
    ("11:00", "12:00", "11:00 AM - 12:00 PM"),
    ("10:00", "11:00", "10:00 AM - 11:00 AM"),
    ("15:00", "16:00", "3:00 PM - 4:00 PM"),
    ("14:00", "15:00", "2:00 PM - 3:00 PM"),
    ("12:00", "13:00", "12:00 PM - 1:00 PM"),
    ("13:00", "14:00", "1:00 PM - 2:00 PM"),
]


def send_notification(subject: str, body: str):
    if not all([NOTIFY_TO, NOTIFY_FROM, NOTIFY_PASS]):
        log(f"Skipping email notification (missing env vars). Subject: {subject}", "WARNING")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = NOTIFY_FROM
        msg["To"] = NOTIFY_TO
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_FROM, NOTIFY_PASS)
            server.send_message(msg)
        log(f"Email sent: {subject}")
    except Exception as e:
        log(f"Failed to send email notification: {e}", "ERROR")


def is_enabled() -> bool:
    if os.path.exists("config.yml"):
        with open("config.yml", "r") as f:
            for line in f:
                if line.strip().startswith("enabled:"):
                    return "true" in line.lower()
    return True


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
        r_start = parse_time_str(parts[0])
        r_end = parse_time_str(parts[1])
        return s_time >= r_start and e_time <= r_end
    except Exception:
        return False


def book_court(headless: bool = True):
    log("=== court_booker run started ===")

    if not is_enabled():
        log("Script disabled via config.yml. Exiting.", "WARNING")
        return

    if not USERNAME or not PASSWORD:
        log("Missing BL_USERNAME or BL_PASSWORD environment variables.", "ERROR")
        sys.exit(1)

    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    target_date = (now + timedelta(days=8)).strftime("%Y-%m-%d")
    url = get_reservation_url(target_date)

    log(f"Target date: {target_date}")
    log(f"Navigating to booking URL (headless={headless})")

    with sync_playwright() as p:
        browser, context, page = create_browser_context(p, headless=headless)

        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        log(f"Initial page loaded. URL: {page.url}")

        # Handle login redirect using shared helper
        login_if_needed(page, USERNAME, PASSWORD, log_fn=log)

        deadline = time_module.time() + 240
        retry_count = 0
        while True:
            raw_landed = page.url.split("selectedDate=")[-1] if "selectedDate=" in page.url else ""
            try:
                landed_date = parse_date(raw_landed).strftime("%Y-%m-%d") if raw_landed else ""
            except Exception:
                landed_date = raw_landed

            if landed_date == target_date:
                log(f"Correct date confirmed: {landed_date}")
                break

            if time_module.time() > deadline:
                msg = f"Page redirected to unexpected date after 4 mins. Target: {target_date}, Landed: {landed_date}"
                log(msg, "ERROR")
                send_notification("Tennis Court Booking Failed — Redirect Error", msg)
                browser.close()
                return

            retry_count += 1
            log(f"Date not yet available (landed: {landed_date}), retry #{retry_count} in 6s...", "DEBUG")
            time_module.sleep(6)
            page.goto(url, wait_until="domcontentloaded", timeout=15000)

        unavail = page.query_selector("text=This Amenity is currently unavailable")
        if unavail:
            msg = f"Amenity unavailable on target date {target_date}."
            log(msg, "WARNING")
            send_notification("Tennis Court Booking Failed — Unavailable", msg)
            browser.close()
            return

        avail_table = None
        try:
            avail_table = page.wait_for_selector("#ctl00_ContentPlaceHolder1_AvailabileTimeSlotsList", timeout=5000)
        except Exception:
            pass

        if not avail_table:
            msg = f"Availability table not found for date {target_date}."
            log(msg, "ERROR")
            send_notification("Tennis Court Booking Failed — UI Element Missing", msg)
            browser.close()
            return

        td_elements = avail_table.query_selector_all("td")
        available_ranges = [td.inner_text().strip() for td in td_elements if td.inner_text().strip()]
        log(f"Available slots: {available_ranges}")

        if not available_ranges:
            msg = f"No available time slots found on {target_date}."
            log(msg, "WARNING")
            send_notification("Tennis Court Booking Failed — No Slots Available", msg)
            browser.close()
            return

        selected_slot = None
        for s_start, s_end, label in PRIORITY_SLOTS:
            if any(is_slot_in_range(s_start, s_end, r) for r in available_ranges):
                selected_slot = (s_start, s_end, label)
                break

        if not selected_slot:
            msg = f"No preferred time slot available on {target_date}. Available ranges: {', '.join(available_ranges)}"
            log(msg, "WARNING")
            send_notification("Tennis Court Booking Failed — Preferred Slots Taken", msg)
            browser.close()
            return

        s_start, s_end, label = selected_slot
        log(f"Selected slot: {label} ({s_start} - {s_end})")

        start_input = page.query_selector("#ctl00_ContentPlaceHolder1_StartTimePicker_dateInput")
        end_input = page.query_selector("#ctl00_ContentPlaceHolder1_EndTimePicker_dateInput")

        if start_input and end_input:
            start_input.fill(s_start)
            end_input.fill(s_end)
            page.keyboard.press("Tab")
            log("Time inputs filled.")

        save_btn = page.query_selector("#ctl00_ContentPlaceHolder1_FooterSaveButton, #ctl00_ContentPlaceHolder1_HeaderSaveButton")
        if save_btn:
            save_btn.click()
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                page.wait_for_load_state("domcontentloaded", timeout=5000)

            success_msg = f"Successfully booked tennis court for {target_date} at {label}."
            log(success_msg)
            send_notification("Tennis Court Booked Successfully!", success_msg)
        else:
            msg = f"Save button not found when booking slot {label} on {target_date}."
            log(msg, "ERROR")
            send_notification("Tennis Court Booking Failed — Save Button Missing", msg)

        browser.close()
        log("=== court_booker run complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated tennis court booker.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode (default)"
    )
    group.add_argument(
        "--headful", action="store_true", help="Run browser in headful mode (visible GUI)"
    )

    args = parser.parse_args()

    # Default to headless=True for court_booker unless --headful is specified
    is_headless = False if args.headful else True
    book_court(headless=is_headless)
