# lighthouse-tennis-court-booker

Automated tennis court booking for Lighthouse West (TSCC 2794) via BuildingLink.

## Setup

```bash
poetry install
poetry run playwright install chromium
cp .env.example .env  # fill in your values
```

## Usage

### Scheduled Court Booker (GitHub Actions / Production)

By default, `court_booker.py` runs in live booking mode targeting `+8` days offset (midnight adjustment for scheduled 23:59 ET runs), with headless browser, email notifications, and no HTML file dumps.

```bash
# Production run (headless, +8 days offset, email notifications enabled)
poetry run python court_booker.py

# Optional: Run with visible browser GUI
poetry run python court_booker.py --headful
```

### Dry Run / Manual Testing

Dry run mode (`dry_run.py` or `court_booker.py --dry-run`) defaults to `+7` days offset (exactly 1 week out), disables email notifications, skips clicking Save, and optionally dumps page HTML to `html/`.

```bash
# Run dry run via convenience wrapper (headful GUI by default)
poetry run python dry_run.py

# Run dry run directly via court_booker.py
poetry run python court_booker.py --dry-run

# Options:
poetry run python dry_run.py --headless            # Run without GUI
poetry run python dry_run.py --days 8               # Custom date offset (+8 days)
poetry run python dry_run.py --no-save-html         # Disable HTML file dump
poetry run python dry_run.py --interactive          # Pause before closing browser
```

## Config

Set `enabled: false` in `config.yml` to pause the pipeline without touching the workflow.

## Deployment

Add the variables from `.env.example` as GitHub Actions Secrets, then push to main.
