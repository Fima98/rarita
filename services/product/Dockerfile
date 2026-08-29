# STAGE 1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app


COPY pyproject.toml uv.lock ./
COPY services/product/pyproject.toml services/product/
RUN uv sync --package product --frozen --no-dev

COPY protos/product ./protos/product
COPY services/product ./services/product

RUN uv run python -m grpc_tools.protoc -I protos \
    --python_out=services/product \
    --grpc_python_out=services/product \
    protos/product/product.proto

RUN find services/product -type d -exec touch {}/__init__.py \;

# STAGE 2
FROM python:3.12-slim-bookworm
WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "services/product/main.py"]