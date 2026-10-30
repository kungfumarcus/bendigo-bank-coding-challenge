# Commission Quote App

Take-home code challenge: a web app where lending staff enter loan details and get a commission quote from a mock third-party vendor Commission Quote API.

## With more time

- Vendor key from a secrets manager instead of `.env`
- HTTPS to the vendor (plain HTTP inside the local Docker network today)
- User authentication (SSO) and rate limiting on our own API
- Integration tests of the backend against a running vendor mock
- Browser end-to-end tests and a CI pipeline
- Dependency scanning (`pip-audit`, `npm audit`, Dependabot) and pre-commit hooks
- Localisation of user-facing text; the backend already sends only codes, so this is frontend-only

## AI usage

<!-- Agents: one short line per entry naming the action — no rationale or who-agreed detail. -->

### Commit 1: Setup
- Reviewed the challenge PDF
- Created the private GitHub repo `bendigo-bank-coding-challenge`
- Added `CLAUDE.md` with basic rules
- Created `docs/` with the decision register and challenge brief
- Added `.gitignore` and `.gitattributes`
- Added decisions D1-D2

### Commit 2: Spec
- Brainstormed the solution design
- Wrote the spec in `docs/`: overview, vendor API, backend, frontend, running
- Added decisions D3–D7
- Ran thirteen cold spec reviews and addressed their findings
- Ran a web app best practices review and added the agreed hardening
