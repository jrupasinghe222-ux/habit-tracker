# Authentication decision for the first milestone

Use Supabase browser Auth with Google OAuth, PKCE, and tab-scoped sessionStorage. The frontend sends the Supabase access token in the Authorization header. FastAPI does not use authentication cookies, does not trust a browser user ID, and does not accept an owner field in habit input.

FastAPI validates ES256/RS256 signatures against the configured Supabase project's JWKS endpoint; it checks issuer, audience, required timestamps, expiry, non-anonymous authenticated role and UUID subject. Unknown, expired, malformed and forged tokens fail closed. Verification-service failures return a generic 503. JWKS are cached for five minutes, in addition to any upstream cache; signing-key changes need rollout care.

This avoids a custom server session store for the learning milestone. Browser token storage still requires strong XSS prevention: React renders habit names as text, and no raw HTML injection is used. Session data is cleared from the UI on auth state changes, and in-flight responses are ignored after account changes. A deployment-specific Content Security Policy and browser checks are release requirements.

Logout clears the local session and refresh token. Existing access tokens can remain valid until expiration; immediate access-token revocation is not implemented. Choose a suitably short token lifetime in the development project and verify behavior before launch.

API ownership filters and PostgreSQL row-level security both restrict habit data. Tests use synthetic test-only signing keys and mock key retrieval; production has no bypass switch. SQLite API tests do not validate the PostgreSQL policy or runtime role.
