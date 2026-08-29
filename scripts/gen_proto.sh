#!/bin/bash
# Для Product Service
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/product \
  --grpc_python_out=services/product \
  protos/product/product.proto

# Для Gateway (генеруємо контракти всіх сервісів)
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/gateway \
  --grpc_python_out=services/gateway \
  protos/product/product.proto