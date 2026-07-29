# lighthouse-tennis-court-booker

Automated tennis court booking for Lighthouse West (TSCC 2794) via BuildingLink.

## Setup

```bash
poetry install
poetry run playwright install chromium
cp .env.example .env  # fill in your values
```

## Usage

### Scheduled Court Booker

```bash
# Default (headless mode)
BL_USERNAME=username BL_PASSWORD=your_password poetry run python court_booker.py

# Optional: Run with visible browser GUI
poetry run python court_booker.py --headful
```

### Dry Run (DOM inspection — run before deploying)

```bash
# Default (headful mode so you can watch)
BL_USERNAME=username BL_PASSWORD=your_password poetry run python dry_run.py

# Optional: Run headlessly (e.g. on headless server / CI)
poetry run python dry_run.py --headless
```

## Config

Set `enabled: false` in `config.yml` to pause the pipeline without touching the workflow.

## Deployment

Add the variables from `.env.example` as GitHub Actions Secrets, then push to main.
