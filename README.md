# Habit Tracker

A guided React + FastAPI + Supabase project.

## Current milestone

Supabase Google sign-in is enabled. Migrations 0001 and 0002 are applied and the restricted runtime database connection is configured in the ignored root .env. Real PostgreSQL access-isolation checks pass. Vercel deployment and the full browser save/refresh workflow remain to be verified.

Verified locally:
- 31 tests pass: health, signed-token validation, input validation, and API user isolation.
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
| frontend/src/supabase.ts | Browser auth client, PKCE, tab-scoped session persistence |
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

First habit-storage slice only: create/list/edit/delete, at most 100 listed habits. Scheduling, daily completions, streaks, pagination, abuse controls, export, account deletion, backups, and release-level browser/production checks remain to be built. API isolation tests use SQLite and do not prove PostgreSQL RLS behavior. Logout clears the local session; issued bearer tokens can remain valid until expiry.

Free hosting is subject to provider limits. Vercel Hobby must qualify as personal, non-commercial use. No public launch or unlimited-capacity/security guarantee is claimed.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the full release requirements.
