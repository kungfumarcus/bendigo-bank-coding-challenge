FROM python:3.12.11-slim-bookworm AS build
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.12.8
WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen
COPY app ./app
COPY tests ./tests
RUN uv run --frozen ruff check . \
    && uv run --frozen ruff format --check . \
    && uv run --frozen mypy --strict app tests
RUN uv sync --frozen --no-dev

FROM python:3.12.11-slim-bookworm AS runtime
RUN useradd --system --no-create-home appuser
WORKDIR /srv
COPY --from=build /srv/.venv ./.venv
COPY --from=build /srv/app ./app
USER appuser
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
