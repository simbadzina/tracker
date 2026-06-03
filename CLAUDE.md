# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Flask app that tracks a daily success/failure streak on a visual multi-month calendar. State (which days are "successful"/"unsuccessful") lives in a DynamoDB table keyed by date. There is a public read-only page and a secret admin page where days are toggled.

## Commands

```bash
pip install -r requirements.txt          # install deps
python app.py                            # run dev server (debug, port 5000)
gunicorn --bind 0.0.0.0:8000 --workers 1 --preload app:app   # production (as in Dockerfile)

# CLI for editing day statuses directly in DynamoDB (bypasses the web app)
python cli.py mark YYYY-MM-DD successful|unsuccessful|unset
python cli.py show       # calendar view of marked days
python cli.py status     # streak + counts
```

There is no test suite, linter, or build step.

## Required environment

`.env` (loaded via python-dotenv) must define AWS credentials and:
- `DYNAMODB_TABLE` — table name (default `tracker`), key schema: `date` (String `YYYY-MM-DD`) as HASH key; items hold `status` ("successful"|"unsuccessful") and a timestamp.
- `ADMIN_PATH` — **required; `app.py` raises at import if unset.** The admin calendar is mounted at `/<ADMIN_PATH>` as a deliberately unguessable URL — that path is the only access control on write operations. Never hardcode or commit a real value.

See `DYNAMODB_SETUP.md` for table/IAM creation and `RENDER_DEPLOYMENT.md` for deployment.

## Architecture notes

- **`app.py` is the whole backend.** Routes: `/` (public `index.html`), `/<ADMIN_PATH>` (registered dynamically via `add_url_rule`, serves `admin.html`), `/health`, and the `/api/*` JSON endpoints. `index.html` only calls `/api/streak`; `admin.html` also calls `/api/marked-days` and `/api/toggle-day`.

- **Streak semantics live entirely in `get_streak`.** The streak counts consecutive `successful` days walking backward from the most recent success. An `unsuccessful` day breaks the streak; an *unmarked* day stops counting but does not break it (partial streaks are preserved). `success_rate` is over marked days only. `START_DATE` is hardcoded in `app.py` (currently `date(2026, 1, 1)`) and bounds both the calendar and all counting.

- **Two caches, both module-level globals, easy to get wrong:**
  1. `get_cached_marked_days()` — 30s TTL cache of the full DynamoDB scan. Any write (`/api/toggle-day`) must call `invalidate_cache()` or the UI shows stale data.
  2. `get_calendar_data()` — `@lru_cache` keyed on today's date string (so it recomputes once per day). It generates the list of months from `START_DATE` through the current month.
  Because these are in-process globals, they are per-worker — run a single gunicorn worker (the Dockerfile does) or workers will hold divergent caches.

- **`/api/streak` returns everything in one payload** (streak, counts, `months_data`, and the full `marked_days` map) specifically so the frontend avoids a second round-trip. Keep this in mind before "cleaning up" the response shape — the templates read these exact keys.

- **`cli.py` reimplements its own DynamoDB access and streak logic** independently of `app.py` (it does not share the caching or the backward-walk algorithm). Editing streak rules means changing both files if you want them to agree.

- **Toggle cycle** (`/api/toggle-day`): unmarked → successful → unsuccessful → unmarked, where unmarked deletes the DynamoDB item. The client sends the current status; the server computes the next.
