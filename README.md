# lighthouse-tennis-court-booker

Automated tennis court booking for Lighthouse West (TSCC 2794) via BuildingLink.

## Setup

```bash
poetry install
poetry run playwright install chromium
cp .env.example .env  # fill in your values
```

## Dry run (DOM inspection — run before deploying)

```bash
BL_USERNAME=username BL_PASSWORD=your_password poetry run python dry_run.py
```

## Config

Set `enabled: false` in `config.yml` to pause the pipeline without touching the workflow.

## Deployment

Add the variables from `.env.example` as GitHub Actions Secrets, then push to main.
