# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/order/pyproject.toml services/order/
RUN uv sync --package order --frozen --no-dev

COPY protos ./protos
COPY services/order ./services/order

RUN uv run python -m grpc_tools.protoc -I protos \
    --python_out=services/order \
    --grpc_python_out=services/order \
    protos/order/order.proto \
    protos/product/product.proto

RUN find services/order -type d -exec touch {}/__init__.py \;

# STAGE 2: Runner
FROM python:3.12-slim-bookworm
WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "services/order/main.py"]