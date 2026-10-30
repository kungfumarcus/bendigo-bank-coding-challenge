# Running

How to run the solution with Docker Compose or locally for development, including tests, lint and type checks.

## Config files

- `backend/.env` — copied from `backend/.env.example`
- `vendor-mock/.env` — copied from `vendor-mock/.env.example`
- Each `.env.example` lists its component's required settings, and every other setting commented out at its code default; the two must stay in step
- Real environment variables take precedence over `.env`
- `VENDOR_API_KEY` must match in both for quotes to succeed; both `.env.example` files hold the same non-secret placeholder key, which any real deployment must replace
- `backend/.env.example` holds the local-dev `VENDOR_QUOTE_URL`, `http://localhost:9000/commission-quotes`
- The frontend has no config

## Ports

- The backend listens on port 8000 and the vendor mock on 9000 in both run paths

## Docker

Prerequisite: Docker with Compose.

1. Copy both `.env.example` files to `.env`
2. `docker compose up --build`
3. Open `http://localhost:8080`

Topology, in one `compose.yaml`:

- `app-net` — `frontend` and `backend`
- `vendor-net` — `backend` and `vendor-mock`; the backend's route to the vendor
- Only `frontend` publishes a port (`8080`); nginx serves the built app and proxies `/api/*` to `backend` with the path kept as is (no prefix stripping)
- Each service reads its own `env_file`; Compose overrides `VENDOR_QUOTE_URL` to the in-network address `http://vendor-mock:9000/commission-quotes`
- `backend` has a Compose `healthcheck` on `GET /api/v1/health`, probed with Python itself since the slim image has no `curl`; `frontend` waits for it with `depends_on: condition: service_healthy`
- `docker compose logs` shows the JSON logs from both Python apps

Images:

- Multi-stage builds — a build stage installs dependencies and runs lint and type checks (and `vite build` for the frontend); the runtime stage holds only what runs: a virtual environment without dev dependencies (`uv sync --frozen --no-dev`) and `app/` on a slim Python image, or the built `dist/` on nginx
- Every container runs as a non-root user; nginx uses an unprivileged image and listens on 8080 inside the container
- Base images are pinned to exact versions, not floating tags
- Each component has a `.dockerignore` excluding `.env`, `.venv/`, `node_modules/`, `.git/` and caches, so no `.env` ever reaches an image

nginx:

- `Cache-Control: no-store` on `/api/*`; long cache for hashed static files; `no-cache` for `index.html`
- Security headers on every response, including `/api/*` and error responses: a `Content-Security-Policy` allowing only same-origin resources with `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; a `location` block that adds its own headers must repeat them, since nginx drops inherited `add_header` there
- `server_tokens off`
- `client_max_body_size` small (a quote request is well under 1 KB)

## Reproducible builds

- Lockfiles are committed: `uv.lock` in each Python component, `package-lock.json` in `frontend/`
- Runtime versions are pinned in `.python-version` and `frontend/.nvmrc`
- Installs use the lockfiles: `uv sync --frozen` and `npm ci`

## Local development

Prerequisites: Python 3.12, uv, Node.js 22.

1. Copy both `.env.example` files to `.env`
2. Vendor mock: in `vendor-mock/`, `uv run uvicorn app.main:app --port 9000`
3. Backend: in `backend/`, `uv run uvicorn app.main:app --port 8000`
4. Frontend: in `frontend/`, `npm ci` then `npm run dev`; Vite proxies `/api` to `http://localhost:8000`
5. Open the URL Vite prints

## Tests

- Backend and vendor mock: `uv run pytest` in each
- Frontend: `npm test` — Vitest with React Testing Library

## Lint and type checks

- Backend and vendor mock: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict app tests` in each
- Frontend: TypeScript in `strict` mode; `npm run lint` (eslint), `npm run format:check` (`prettier --check`) and `npm run typecheck` (`tsc`)
