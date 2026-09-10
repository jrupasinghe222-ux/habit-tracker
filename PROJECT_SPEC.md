# Habit Tracker — project specification

Status: Google provider enabled; database migrations 0001 through 0003 applied; restricted app connection configured; live PostgreSQL isolation checks and 42 local tests pass. Browser save/refresh verification and Vercel deployment remain pending.

## Purpose

Build a responsive, multi-user habit tracker while teaching the owner how to direct Codex, review changes, test behavior, and deploy safely. Explain each milestone and provide reproducible commands. Build in small working steps.

## Stack and budget

- Frontend: React, TypeScript, Vite, Tailwind CSS.
- Backend: Python, FastAPI, SQLAlchemy, Alembic.
- Database: Supabase PostgreSQL.
- Authentication: Google sign-in through Supabase Auth. No email/password signup in the first release.
- Hosting: Vercel, using a same-origin /api routing arrangement where supported by the chosen deployment layout.
- Version control and checks: GitHub and GitHub Actions.
- Tests: pytest, HTTPX, Playwright.
- Use free plans and provider subdomains. Do not enable paid services or chargeable overages without authorization. Vercel Hobby requires personal, non-commercial use. Free quotas and availability limits are not a production uptime guarantee.

## First deployed milestone

1. User opens the deployed app and signs in with Google.
2. FastAPI validates the Supabase access token, including signature, issuer, audience, and expiry.
3. User creates a named daily habit.
4. The habit is stored in PostgreSQL and remains visible after refresh and a fresh login.
5. Another signed-in user cannot list, read, modify, or delete it.
6. User can log out, and the interface clears private cached data.

Deploy a frontend and backend health endpoint early, then add this complete workflow. Do not present mock data or simulated authentication as a working deployment. Enable public use only after essential authorization and persistence checks pass.

## First public release

- Google login, logout, and session expiry handling.
- Profile with an IANA timezone; browser timezone is the initial suggestion.
- Create, edit, archive, and delete habits.
- Daily or selected-weekday schedules.
- Mark and undo completion for today or past scheduled days; reject future dates.
- Completion history, weekly progress, streaks, and a calendar.
- Mobile and desktop layouts, keyboard access, visible focus, labeled controls, and readable contrast.
- Loading, empty, error, and retry states.
- Export personal data and delete the account and associated application data.
- Database migrations, automated checks, safe logs, health checks, and a tested backup/restore procedure.

Reminders, social features, payments, native mobile apps, and AI features are deferred.

## Data model direction

- profiles: Supabase user ID, timezone, timestamps.
- habits: ID, owner ID, name, archive state, timestamps.
- habit_schedule_versions: habit ID, effective local date, selected weekdays. Preserve historical schedules when edited.
- completions: habit ID, owner ID, local completion date, creation timestamp.
- Enforce one completion per habit and local date with a database unique constraint.
- Use timezone-aware UTC timestamps for events and calendar dates for daily completions.
- Resolve and document timezone changes before implementing streaks. Historical completion dates must not silently shift.
- A streak counts consecutive scheduled dates, skips unscheduled dates, and is not broken by an incomplete current day until that local day ends.
- Cascade application data deletion appropriately. Account deletion must also remove the Supabase Auth identity using a server-only administrative operation with recoverable failure handling.

## Security requirements

- Derive the owner ID from the validated identity, never from a trusted client-supplied owner field.
- Scope every database operation to that owner, including exports and aggregate statistics.
- Use a dedicated least-privilege database role and parameterized queries.
- Explicitly secure Supabase's exposed Data API: disable access to application tables or apply tested row-level security policies. FastAPI checks alone must not leave a second API exposed.
- Do not assume row-level security protects queries made with a role that bypasses it.
- Keep database credentials and Supabase secret/service-role keys server-only. Public frontend variables may contain only intentionally public configuration.
- Choose and document session transport before authentication implementation. For cookie authentication, implement Secure/HttpOnly cookies and CSRF protection; for bearer authentication, restrict token exposure and clear session data correctly.
- Configure explicit origins, redirects, environment separation, validation limits, and abuse controls appropriate to serverless hosting. Do not rely on process-local state for global rate limits.
- Logs must exclude tokens, credentials, and habit contents.
- Test environments may mock identity; production must have no authentication bypass.

## Release checks

- Automated API tests for invalid/expired credentials and cross-user access on every private resource.
- Database integration tests against PostgreSQL, including duplicate/retried check-ins and migrations.
- Test scheduled-day streak calculations, local midnight, daylight-saving transitions, and archive behavior.
- Browser checks for login integration, create/edit/check/uncheck, persistence after refresh, logout, and mobile/keyboard use.
- Production build, type checks, linting, dependency review, and secret checks pass.
- Run load tests against a local or explicitly permitted environment; do not load-test Vercel without provider authorization.
- Verify backup restoration in an isolated database and document data-loss exposure and recovery steps.
- Verify the deployed critical workflow and release rollback procedure.
- Record measured capacity and free-tier constraints; do not claim zero vulnerabilities or unlimited users.

## Milestones

1. Project specification and environment inventory.
2. Reproducible local toolchain, frontend/backend skeleton, and health check.
3. Early Vercel deployment and configuration of Supabase/Google authentication.
4. First complete habit workflow with isolation tests.
5. Scheduling, completions, progress, and accessibility.
6. Export/deletion, operational checks, and public release verification.

## External setup still needed

- Connect the existing GitHub account to a public repository.
- Supabase project, database connection settings, and Google provider are configured for local development.
- Google Cloud OAuth client, consent/audience setup, and permitted redirect URLs.
- Vercel account, project configuration, and environment variables.

Keep secrets in local ignored environment files or hosting secret settings, not in chat or committed files. Sign-in and account authorization steps may require the owner to interact with the provider.
