# STAGE 1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/gateway/pyproject.toml services/gateway/
RUN uv sync --package gateway --frozen --no-dev

COPY protos ./protos
COPY services/gateway ./services/gateway

RUN uv run python -m grpc_tools.protoc -I protos \
    --python_out=services/gateway \
    --grpc_python_out=services/gateway \
    protos/*/*.proto

RUN find services/gateway -type d -exec touch {}/__init__.py \;

# STAGE 2
FROM python:3.12-slim-bookworm
WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/services/gateway"

CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]