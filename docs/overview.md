# Overview

The Commission Quote App as a whole: its components, where trust boundaries sit, the phases, and what counts as done.

## Documents

- [`brief.md`](brief.md) — the challenge brief as received
- [`decisions.md`](decisions.md) — the impactful decisions, one line each
- [`vendor-api.md`](vendor-api.md) — the vendor mock: contract, key check, pricing and simulated faults
- [`backend.md`](backend.md) — our FastAPI service: layers, endpoints, validation, vendor retry, errors and logging
- [`frontend.md`](frontend.md) — the React page: form, states, result formatting and error messages
- [`running.md`](running.md) — how to run with Docker or locally, including tests, lint and type checks

## Components

```text
browser ──► frontend (React, built and served by nginx)
               │  /api/* proxied — same origin, no CORS
               ▼
            backend (FastAPI) ── holds the vendor api-key, validates, retries, maps errors
               │  vendor network only
               ▼
            vendor-mock (FastAPI) ── stands in for the third-party Commission Quote API
```

- **frontend** — the staff-facing page: loan form, quote result, errors
- **backend** — our service; the only component that talks to the vendor
- **vendor-mock** — a stand-in for the third-party vendor, built to the agreed contract; replaced by the real vendor by changing the backend's URL and key

## Security

- The vendor `api-key` exists only in the backend's and the vendor mock's server-side config; it never reaches the browser or logs, and no real key is ever committed
- The browser can reach only the frontend; the backend is reached through the frontend's proxy, and the vendor mock only from the backend
- The vendor is untrusted; how its replies are checked and contained is in [`backend.md`](backend.md) § Vendor retry and § Error responses
- Errors shown to users carry safe text and the request ID, never internal detail

## Quality bar

Every build runs its component's lint and type checks — in Docker, during the image build — and a failure fails the build. Tools and commands are in [`running.md`](running.md) § Lint and type checks.

## Phases

1. Spec — this `docs/` folder, reviewed until sound
2. Implementation — the three components to this spec
3. Testing — the tests in each component spec, lint and type checks
4. README — run and test instructions, AI usage, and improvements with more time

## Definition of done

Applies at the end of phase 4. Evidence cited: test and lint output for the checks, and a screenshot of the happy path on the running app.

The listed tests are deliberately few — the brief asks for the ones that matter most. Specified behaviour without a listed test (security headers, health checks, request ID, logging, frontend states beyond those listed) is checked by the manual run, not automated.

- All tests pass
- All lint and type checks pass
- `docker compose up --build` works from a fresh clone by following the README
- The local-dev steps work as written
- The happy path, and a simulated vendor failure showing its error message, have been shown working on the running app
- Every backend error code is covered by a test
- The README has run and test steps, AI usage, and improvements with more time

## Out of scope

- An idempotency key on vendor retries
- Error formats for unknown routes or methods (404, 405)
- Accessibility beyond labels, linked errors, the busy state and the alert banner (no focus management or `aria-live`)
- Passing the request ID to the vendor
- A health check on the vendor mock, which stands in for a third party
- Treating loan inputs in logs as sensitive; they are business data, not personal data
- A request size limit in the backend itself; nginx enforces it
