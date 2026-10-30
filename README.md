# Commission Quote App

Take-home code challenge: a web app where lending staff enter loan details and get a commission quote from a mock third-party vendor Commission Quote API.

## Run with Docker

Prerequisite: Docker with Compose.

```bash
cp backend/.env.example backend/.env
cp vendor-mock/.env.example vendor-mock/.env
docker compose up --build
```

Open <http://localhost:8080>. The vendor mock fails about 20% of requests and is slow for about 10% on purpose; the backend retries once, so an occasional error message is expected.

## Run locally

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22.

Copy both `.env.example` files to `.env` as above, then in three terminals:

```bash
cd vendor-mock && uv run uvicorn app.main:app --port 9000
```

```bash
cd backend && uv run uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm ci && npm run dev
```

Open the URL Vite prints.

## Tests and checks

In `backend/` and `vendor-mock/`:

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict app tests
```

In `frontend/`:

```bash
npm test
```

```bash
npm run lint && npm run format:check && npm run typecheck
```

The spec is in [`docs/`](docs/overview.md).

## With more time

- Vendor key from a secrets manager instead of `.env`
- HTTPS to the vendor (plain HTTP inside the local Docker network today)
- User authentication (SSO) and rate limiting on our own API
- Integration tests of the backend against a running vendor mock
- Browser end-to-end tests and a CI pipeline
- Dependency scanning (`pip-audit`, `npm audit`, Dependabot) and pre-commit hooks
- An idempotency key on vendor calls: when a slow reply times out, the vendor may already have issued a quote, and the retry then creates a second one

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

### Commit 3: Implementation
- Implemented the docker compose
- Added run and test steps to this README
- Ran tests, lint and type checks for all three components
- Ran the app locally and checked the happy path and a simulated vendor failure in a browser
- Ran the Docker Compose stack and checked its nginx headers, non-root users and network isolation
- Ran a code review of the implementation and fixed the findings
- Added decisions D8–D9

### Commit 4: Final Checks
- Ran a final review, fixed some minor issues and retested
