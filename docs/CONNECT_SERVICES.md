# Lesson 2: connect Google sign-in, PostgreSQL, and hosting

These instructions describe setting up a new installation. The current development project already has Supabase authentication and database access configured; GitHub and Vercel setup are next. Work in the project root folder. Use a new Supabase development project; the migration deliberately refuses to reuse a conflicting app role or schema.

## 1. Create the Supabase project

1. Sign in at https://supabase.com/dashboard and create a project on the Free plan.
2. Use a clear name such as habit-tracker-dev. Choose a region near your initial users (for Sri Lanka, compare the available nearby regions).
3. Generate a strong database password and save it in your password manager.
4. Wait for provisioning.
5. Find the project URL and publishable API key in the project's Connect/API settings.
6. Copy root .env.example to .env, and frontend/.env.example to frontend/.env.local.
7. Put the project URL in both files and the publishable key only in the frontend file.

The publishable key is meant for browser use. A secret/service-role key and database password are not. Do not paste secrets into chat or commit them.

Root .env:
    SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co

frontend/.env.local:
    VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
    VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...

Use the public project URL/key to identify the project. The login token, not the publishable key, identifies the signed-in user.

## 2. Configure Google login

1. In Supabase Authentication > Sign In / Providers, select Google. Copy its callback URL.
2. Create/select a project in Google Cloud Console and configure Google Auth Platform.
3. Configure branding and an External audience. While in Testing, add your own Google account as a test user.
4. Request only basic identity scopes: openid, email, profile.
5. Create an OAuth client of type Web application.
6. Add the Supabase callback URL as the authorized redirect URI. It is normally:
       https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
7. Save the Google client ID and client secret in Supabase's Google provider settings, then enable Google.
8. In Supabase URL Configuration, set the local Site URL to http://127.0.0.1:5173 and allow this exact redirect:
       http://127.0.0.1:5173/auth/callback
9. Use that same browser address consistently. localhost and 127.0.0.1 are different origins.

There are two redirects: Google returns to Supabase, and Supabase returns to our frontend. Putting the frontend URL in Google's callback field will not work.

In Supabase's JWT Signing Keys settings, use an asymmetric signing key (ES256 recommended; RS256 is also supported by this app). This implementation intentionally rejects legacy HS256 tokens. Do not rotate an existing production project's keys just to follow this tutorial; use the new development project.

Before public launch, configure the Google audience/publishing status for public users and complete any branding/verification requirements Google presents. We will test with two real accounts before opening registration broadly.

Reference: https://supabase.com/docs/guides/auth/social-login/auth-google

## 3. Create the database schema

The versioned migration is migrations/versions/0001_habits.py. It creates:
- habit_app.habits in a private schema;
- an owner reference to auth.users;
- a restricted habit_api role;
- row-level security enforcing the transaction's authenticated owner;
- no access for browser-facing anon/authenticated database roles.

Do not expose habit_app through Supabase's Data API.

From Supabase Connect, copy a direct or session-pooler admin URI (port 5432) into MIGRATION_DATABASE_URL in the root .env. Use session pooling if your connection does not support IPv6. Encode special password characters correctly in connection URIs.

Run from the project root:
    .\.venv\Scripts\python.exe -m alembic upgrade head

Migration requires database-owner privileges and should run only from a trusted local terminal or a protected deployment job. It must never run automatically on each API request.

The migration creates habit_api with NOLOGIN. In Supabase SQL Editor, set a NEW strong password for that application role:
    ALTER ROLE habit_api LOGIN PASSWORD '<new application-only password>';

Type this directly in your trusted dashboard and store it in your password manager. Do not save a filled-in SQL statement to the repository.

Copy the transaction pooler URI (port 6543), change the username from postgres.PROJECT_REF to habit_api.PROJECT_REF, and use the application role's password. Set DATABASE_URL in root .env. The backend refuses the postgres admin username.

The backend disables prepared statements and uses NullPool because Supabase handles transaction pooling. RLS's user ID is set locally inside each transaction and is not left on pooled connections.

Reference: https://supabase.com/docs/guides/database/connecting-to-postgres

## 4. Run and verify locally

Restart Vite after changing frontend environment variables and restart FastAPI after changing backend variables.

Terminal 1:
    .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

Terminal 2:
    npm.cmd --prefix frontend run dev

Open http://127.0.0.1:5173. Sign in, create a habit, refresh, then delete it. Sign out and repeat with a second Google account. Each account must see only its own habits.

Authentication uses Supabase-managed bearer tokens stored in browser localStorage (persists across browser restarts). FastAPI verifies signatures, expiry, issuer, audience, role and user ID. The browser attaches tokens in Authorization headers; the backend does not accept an identity cookie or client-supplied owner_id. Protecting the frontend from script injection remains essential. Local logout clears the local session; an already-issued token can remain valid until expiry. Immediate token revocation is not implemented in this milestone.

The tests include real cryptographic verification using test-only signing keys and SQLite-backed API isolation tests. SQLite does NOT validate PostgreSQL policies. Real database/RLS checks are required before public release.

This first slice lists at most 100 habits; pagination, abuse controls, daily completions and full account management are still release work.

## 5. GitHub and Vercel

Create an empty PUBLIC GitHub repository under your personal account, named habit-tracker (or another available name). Do not initialize it with another README. Link this local repository to its URL only after confirming the destination.

Review all files to be committed and confirm .env and frontend/.env.local are ignored before pushing. Publish only placeholder configuration examples. Public source code does not make the Supabase database or user data public. Keep database credentials, tokens, personal environment notes, and database exports out of Git.

The GitHub workflow runs tests and frontend builds on pushes and pull requests. It has read-only repository permissions and needs no production credentials for its current tests.

In Vercel:
- Import that repository.
- Select the Hobby plan only if the project qualifies for personal non-commercial use.
- Root Directory: repository root, not frontend.
- Framework Preset: Other (vercel.json sets framework to null).
- Build/install/output settings are already in vercel.json.
- Python version is pinned to 3.12 in .python-version.
- Set SUPABASE_URL, DATABASE_URL, VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY in the appropriate environment.
- Do not put MIGRATION_DATABASE_URL or a Google client secret into Vercel for this architecture.
- Do not give untrusted preview deployments production database credentials.

Vercel serves the built frontend and routes /api requests to api/index.py, which exports FastAPI. The callback route serves the frontend. This configuration is prepared but must be verified on a real Vercel deployment.

Add the actual deployed /auth/callback address to Supabase's exact redirect allowlist and update its Site URL. Retain local redirects only for the development project. Avoid broad wildcard callbacks.

Verify the deployed /api/health, login callback, create/read/delete, session expiry, and two-user isolation. A successful build alone is not a deployment test.

Reference: https://vercel.com/docs/functions/runtimes/python/api-directory

## Still required before public release

Live Google/Supabase/Vercel verification; PostgreSQL RLS integration tests; schema migration checks on a clean database; pagination and abuse controls; browser/keyboard/mobile tests; backups and restoration; export/account deletion; dependency review; and the remaining habit-tracking features.

Do not label this milestone production-ready until those release requirements are completed.

## Current database verification

Migration 0001 has been applied to the development Supabase project. A generated application-only password and transaction-pooler connection were saved in ignored .env. The runtime role has no elevated privileges. scripts/verify_database.py passed real PostgreSQL ownership and schema-access checks using temporary rows that were rolled back. Rerun from the root with .\.venv\Scripts\python.exe scripts/verify_database.py. Never publish the migration administrator URL. Restart FastAPI after database environment changes.


Editing milestone: migration 0002 grants UPDATE on the habit name column only. The application role cannot update ownership. Backend ownership tests and live rollback-only PostgreSQL update-isolation checks pass. Each habit card now supports Edit, Save changes, Cancel, and Escape to cancel.
