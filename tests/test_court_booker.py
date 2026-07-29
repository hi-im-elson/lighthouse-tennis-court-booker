from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime, timedelta
import pytz

from court_booker import (
    is_slot_in_range,
    parse_time_str,
    book_court,
)
from utils.notifications import send_notification

DRY_RUN_CFG = {
    "headless": False,
    "days_offset": 7,
    "save_html": True,
    "notifications": False,
}

LIVE_CFG = {
    "headless": True,
    "days_offset": 8,
    "save_html": False,
    "notifications": True,
}


def test_parse_time_str():
    assert parse_time_str("6:00 PM").strftime("%H:%M") == "18:00"
    assert parse_time_str("10:00 AM").strftime("%H:%M") == "10:00"
    assert parse_time_str("18:00").strftime("%H:%M") == "18:00"


def test_is_slot_in_range():
    assert is_slot_in_range("18:00", "19:00", "5:00 PM - 8:00 PM") is True
    assert is_slot_in_range("18:00", "19:00", "10:00 AM - 12:00 PM") is False
    assert is_slot_in_range("18:00", "19:00", "invalid range") is False


@patch("utils.notifications.smtplib.SMTP_SSL")
def test_send_notification_disabled(mock_smtp):
    send_notification("Test Subject", "Test Body", enabled=False)
    mock_smtp.assert_not_called()


@patch("court_booker.create_browser_context")
@patch("court_booker.sync_playwright")
@patch("court_booker.load_config", return_value=DRY_RUN_CFG)
@patch("court_booker.USERNAME", "testuser")
@patch("court_booker.PASSWORD", "testpass")
def test_book_court_dry_run_defaults(mock_load_config, mock_playwright, mock_create_context):
    mock_p = MagicMock()
    mock_playwright.return_value.__enter__.return_value = mock_p
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_create_context.return_value = (mock_browser, mock_context, mock_page)

    tz = pytz.timezone("America/New_York")
    expected_target_date = (datetime.now(tz) + timedelta(days=7)).strftime("%Y-%m-%d")
    mock_page.url = f"https://example.com/?selectedDate={expected_target_date}"
    mock_page.query_selector.return_value = None

    avail_table = MagicMock()
    mock_page.wait_for_selector.return_value = avail_table
    td = MagicMock()
    td.inner_text.return_value = "5:00 PM - 8:00 PM"
    avail_table.query_selector_all.return_value = [td]

    start_input = MagicMock()
    end_input = MagicMock()

    def query_selector_side_effect(selector):
        if "StartTimePicker" in selector:
            return start_input
        if "EndTimePicker" in selector:
            return end_input
        return None

    mock_page.query_selector.side_effect = query_selector_side_effect

    with patch("court_booker.save_page_html") as mock_save_html, \
         patch("court_booker.send_notification") as mock_notify, \
         patch("builtins.input"):
        book_court(profile="dry_run")

        mock_create_context.assert_called_once_with(mock_p, headless=False)
        mock_save_html.assert_called()
        mock_notify.assert_not_called()


@patch("court_booker.create_browser_context")
@patch("court_booker.sync_playwright")
@patch("court_booker.load_config", return_value=LIVE_CFG)
@patch("court_booker.USERNAME", "testuser")
@patch("court_booker.PASSWORD", "testpass")
def test_book_court_live_defaults(mock_load_config, mock_playwright, mock_create_context):
    mock_p = MagicMock()
    mock_playwright.return_value.__enter__.return_value = mock_p
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_create_context.return_value = (mock_browser, mock_context, mock_page)

    tz = pytz.timezone("America/New_York")
    expected_target_date = (datetime.now(tz) + timedelta(days=8)).strftime("%Y-%m-%d")
    mock_page.url = f"https://example.com/?selectedDate={expected_target_date}"

    avail_table = MagicMock()
    mock_page.wait_for_selector.return_value = avail_table
    td = MagicMock()
    td.inner_text.return_value = "5:00 PM - 8:00 PM"
    avail_table.query_selector_all.return_value = [td]

    start_input = MagicMock()
    end_input = MagicMock()
    save_btn = MagicMock()

    def query_selector_side_effect(selector):
        if "StartTimePicker" in selector:
            return start_input
        if "EndTimePicker" in selector:
            return end_input
        if "SaveButton" in selector:
            return save_btn
        return None

    mock_page.query_selector.side_effect = query_selector_side_effect

    with patch("court_booker.send_notification") as mock_notify:
        book_court(profile="court_booker")

        mock_create_context.assert_called_once_with(mock_p, headless=True)
        save_btn.click.assert_called_once()
        mock_notify.assert_called_once()
