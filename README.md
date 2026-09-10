# Habit Tracker

A guided React + FastAPI + Supabase project.

## Current milestone

Supabase Google sign-in is enabled. Migrations 0001 through 0003 are applied and the restricted runtime database connection is configured in the ignored root .env. Real PostgreSQL access-isolation checks pass. Vercel deployment and the full browser save/refresh workflow remain to be verified.

Verified locally:
- 44 tests pass: health, signed-token validation, input validation, and API user isolation.
- Frontend TypeScript check and production build pass.
- Python dependency compatibility passes.
- Alembic generates migration SQL successfully offline.
- Local environment files are ignored by Git.

PostgreSQL row-level security is verified against the live development database. Vercel routing and the full browser save/refresh workflow remain unverified. See [the service setup lesson](docs/CONNECT_SERVICES.md) for exact next steps. The app displays a setup message until valid Supabase public configuration is supplied; it does not simulate login.

## Install

Create a virtual environment first with `py -3.12 -m venv .venv`. Then, from the root folder in PowerShell:
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    npm.cmd --prefix frontend ci

requirements.txt pins runtime packages. requirements-dev.txt adds the test runner. requirements.in and requirements-dev.in record intended dependency ranges; update the pinned files when changing dependencies.

## Run

Backend terminal:
    .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

Frontend terminal:
    npm.cmd --prefix frontend run dev

Open http://127.0.0.1:5173. Use the same hostname configured in Supabase redirects.
Health endpoint: http://127.0.0.1:8000/api/health

VS Code: select .venv\Scripts\python.exe with Python: Select Interpreter. Terminal > Run Task offers backend, frontend, and tests. F5 debugs FastAPI; stop an existing backend on port 8000 first.

## Check

    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m pip check
    npm.cmd --prefix frontend run build

The GitHub workflow runs tests and the frontend build after pushes and pull requests once the repository is connected.

## Where things live

| File/folder | Purpose |
| --- | --- |
| frontend/src/main.tsx | Google login, habit form/list, logout |
| frontend/src/supabase.ts | Browser auth client, PKCE, persistent browser sessions |
| backend/auth.py | Validates signed Supabase access tokens |
| backend/database.py | Restricted PostgreSQL connection and transaction-scoped owner |
| backend/models.py | SQLAlchemy habit model |
| backend/main.py | Health, current user, create/list/edit/delete API routes |
| backend/tests | Automated backend checks; auth tests use test-only keys |
| migrations/versions/0001_habits.py | Database schema and row-level security migration |
| .env.example, frontend/.env.example | Configuration templates; filled copies are ignored |
| vercel.json, api/index.py | Prepared Vercel routing and Python entrypoint |
| docs/CONNECT_SERVICES.md | Guided Supabase, Google, database, and deployment setup |

## Current limitations

First habit-storage slice only: create/list/edit/delete, at most 100 listed habits. Scheduling, streaks, pagination, abuse controls, export, account deletion, backups, and release-level browser/production checks remain to be built. API isolation tests use SQLite and do not prove PostgreSQL RLS behavior. Logout clears the local session; issued bearer tokens can remain valid until expiry.

Free hosting is subject to provider limits. Vercel Hobby must qualify as personal, non-commercial use. No public launch or unlimited-capacity/security guarantee is claimed.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the full release requirements.

## Daily check-ins

Migration 0003 adds private completion history. Run `python -m alembic upgrade head` from a trusted terminal before deploying this version. The migration is additive; existing habits remain intact. Rolling back the application code does not require dropping completion history.

Each habit has a Done today toggle. A second click undoes today's completion. The progress count covers the displayed habits (currently at most 100). Dates use the device's IANA timezone, displayed beside the count; FastAPI calculates the current date. The UI refreshes progress every 30 seconds while visible and on returning to the tab. A request for an old or future date is rejected and prompts a reload. Only today's entries can be changed in this milestone; history remains stored for future progress views.

Different device timezones may show different current dates. There is no saved account timezone setting yet. Existing completion dates do not shift when a device timezone changes.

A database primary key prevents duplicate completions, including concurrent/retried requests. A composite foreign key prevents attributing a completion to someone else's habit. Completion rows have forced row-level security and are deleted with their habit. The rollback-only PostgreSQL check covers these protections.

Manual browser checks: mark done, refresh, reopen the site, undo, compare a second account, and verify the layout on mobile. Use a disposable habit when testing deletion. Streaks and history charts are not yet implemented.

## Weekly history

The last seven days include today in the displayed device timezone. Select a bar to see completed habits on that date. Totals count check-ins, not completion percentages or streaks. History follows the current list of at most 100 habits; renamed habits display their current name, and deleted habits and their history disappear. Empty days show zero check-ins. No new migration is required.

## Date-specific task operations

Migration 0004 adds private `day_tasks` snapshots. The frontend now uses `/api/calendar` and `/api/days/{date}/tasks`. Select a date with the date picker, arrows, or chart. Add, rename, check/uncheck, and delete affect only that calendar date; future days cannot be edited.

Existing recurring habits remain a starting list for dates on or after their creation date. When a date is opened, its snapshot imports any existing check-ins. A dated edit does not modify the underlying recurring default. Newly added tasks belong only to the selected day. Deletion stores a tombstone for that date so the default task cannot reappear after refreshing. Names and completed states on other dates remain intact. Rows belong directly to the authentication user and survive deletion of a legacy habit; deleting the user cascades to their daily task data.

Calendar reads initialize up to seven dated snapshots and require a database transaction. PostgreSQL advisory locks serialize modifications per owner and date; snapshot inserts use ON CONFLICT DO NOTHING. Client-generated IDs make retries of task creation idempotent. The UI caps each date at 100 tasks. Legacy habit endpoints remain for compatibility; the new UI does not use them. Previously deleted records cannot be recovered. Timezone still follows the device, rather than a saved profile.

Validation: 57 backend tests cover date isolation, persistence, deletion tombstones, retry safety, validation, and cross-user blocking. `scripts/verify_database.py` tests live PostgreSQL RLS using rolled-back data. Run migration 0004 before deploying the new frontend; roll back application code without dropping dated records.
