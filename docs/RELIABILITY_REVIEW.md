# Reliability review

Reviewed 2026-09-10.

## Fixes

- Keep editor state and focus across same-account token refreshes. Requests read the current token without remounting task cards.
- Separate stale-read tracking from account/date generations so a failed mutation cannot permanently suppress later refresh responses.
- Clear tasks, drafts, dialogs and pending requests immediately on account changes; ignore delayed responses from the previous account or date.
- Keep the visible list during a reload, retain failed edit drafts, and use friendly connection/timeout messages.
- Cycle Tab and Shift+Tab inside the delete dialog; Escape restores focus to its trigger.
- Honor reduced-motion settings during date navigation.
- Fit long task names and large completion counts at narrow widths; keep date arrows on the same row.

## Automated checks

`npm.cmd --prefix frontend test` runs six component regression tests using Vitest and jsdom. Authentication and network responses are mocked in test files only.

`npm.cmd --prefix frontend run test:browser` runs seven Chromium checks: widths 320, 390, 768 and 1280 pixels; keyboard edit/cancel and dialog focus; failed save with draft preservation; slow reload with a loading announcement. Playwright starts an isolated Vite server on port 5174 and intercepts authentication and API traffic with synthetic test data. The production application has no test authentication switch.

Install its test browser once with `npx playwright install chromium` from the frontend directory. GitHub Actions installs the browser automatically and runs both frontend test suites alongside the backend tests and production build.

## Limits

The browser checks use Chromium with synthetic data. They do not prove real Google account switching, provider outages, physical-device behavior, Safari/Firefox compatibility, screen-reader usability, production load capacity, or absence of security vulnerabilities. Existing signed-token API and PostgreSQL ownership checks complement these UI checks. A real two-account check on the deployed site remains useful after login changes.

Screenshots and traces are generated under frontend/test-results and ignored by Git. Do not capture real login tokens or user data in test fixtures.
