# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Flask app that tracks a daily success/failure streak on a visual multi-month calendar. State (which days are "successful"/"unsuccessful") lives in a DynamoDB table keyed by date. There is one page (`/`): a public read-only calendar that becomes click-to-edit when the owner signs in via Google (restricted to an email allowlist).

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
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth 2.0 Web-application client (Google Cloud Console).
- `GOOGLE_REDIRECT_URI` — must exactly match an Authorized redirect URI on that client (e.g. `https://<host>/callback`; defaults to `http://localhost:5000/callback` for dev).
- `ALLOWED_EMAILS` — comma-separated allowlist of Google emails permitted to edit (case-insensitive). Empty ⇒ nobody can edit; the app still serves read-only.
- `SECRET_KEY` — Flask session-cookie signing key. Must stay stable across restarts or all sessions invalidate. Generate with `python3 -c "import secrets;print(secrets.token_urlsafe(48))"`.

None are *required at import* — a missing Google var just disables login (`/login` 503s, page stays read-only). Never commit real secrets.

See `DYNAMODB_SETUP.md` for table/IAM creation and `RENDER_DEPLOYMENT.md` for deployment.

## Architecture notes

- **`app.py` is the whole backend.** Routes: `/` (renders `index.html`, passing `is_admin`), the OAuth flow (`/login` → Google, `/callback`, `/logout`), `/health`, and the `/api/*` JSON endpoints. `/api/streak` and `/api/marked-days` are public (read-only); **`/api/toggle-day` is guarded by `@admin_required`** (401 unless the session email is on the allowlist) — this is the real write protection, independent of any UI hiding.

- **Auth is session-based Google OAuth, no JWT library.** `/login` sends the user to Google with a `state` (CSRF) param; `/callback` verifies `state`, exchanges the code for tokens server-side over TLS, reads the email from Google's userinfo endpoint, and (if in `ALLOWED_EMAILS`) stores it in `session['email']`. The token is trusted because it came directly from Google over TLS, so the id_token signature is not separately verified. `is_admin()` = session email ∈ allowlist; it both gates `/api/toggle-day` and is passed into `index.html` so the page renders the calendar as clickable. `ProxyFix(x_proto, x_host)` is required so Flask sees `https` behind Caddy (correct redirect scheme + `Secure` cookie).

- **The frontend is one template.** `index.html` always fetches `/api/streak` and renders read-only; when the injected `IS_ADMIN` is true it additionally makes past/today cells `clickable` and POSTs to `/api/toggle-day` (toggle logic was merged in from the old `admin.html`, which no longer exists). The login/logout control is a deliberately faint fixed-position icon in the bottom-right corner.

- **Streak semantics live entirely in `get_streak`.** The streak counts consecutive `successful` days walking backward from the most recent success. An `unsuccessful` day breaks the streak; an *unmarked* day stops counting but does not break it (partial streaks are preserved). `success_rate` is over marked days only. `START_DATE` is hardcoded in `app.py` (currently `date(2026, 6, 1)`) and bounds both the calendar and all counting.

- **Two caches, both module-level globals, easy to get wrong:**
  1. `get_cached_marked_days()` — 30s TTL cache of the full DynamoDB scan. Any write (`/api/toggle-day`) must call `invalidate_cache()` or the UI shows stale data.
  2. `get_calendar_data()` — `@lru_cache` keyed on today's date string (so it recomputes once per day). It generates the list of months from `START_DATE` through the current month.
  Because these are in-process globals, they are per-worker — run a single gunicorn worker (the Dockerfile does) or workers will hold divergent caches.

- **`/api/streak` returns everything in one payload** (streak, counts, `months_data`, and the full `marked_days` map) specifically so the frontend avoids a second round-trip. Keep this in mind before "cleaning up" the response shape — the templates read these exact keys.

- **`cli.py` reimplements its own DynamoDB access and streak logic** independently of `app.py` (it does not share the caching or the backward-walk algorithm). Editing streak rules means changing both files if you want them to agree.

- **Toggle cycle** (`/api/toggle-day`): unmarked → successful → unsuccessful → unmarked, where unmarked deletes the DynamoDB item. The client sends the current status; the server computes the next.
