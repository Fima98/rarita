# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/user/pyproject.toml services/user/
RUN uv sync --package user --frozen --no-dev

COPY protos/user ./protos/user
COPY services/user ./services/user

RUN uv run python -m grpc_tools.protoc -I protos \
    --python_out=services/user \
    --grpc_python_out=services/user \
    protos/user/user.proto

RUN find services/user -type d -exec touch {}/__init__.py \;

# STAGE 2: Runner
FROM python:3.12-slim-bookworm
WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/services/user"

CMD ["python", "services/user/main.py"]