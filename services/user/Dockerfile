# STAGE 1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/user/pyproject.toml services/user/

RUN uv sync --package user --frozen --no-dev

COPY services/user ./services/user

# STAGE 2
FROM python:3.12-slim-bookworm
WORKDIR /app


COPY --from=builder /app /app


ENV PATH="/app/.venv/bin:$PATH"

CMD ["fastapi", "run", "services/user/main.py", "--port", "8001", "--host", "0.0.0.0"]