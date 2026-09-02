#!/bin/bash

# User Service
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/user \
  --grpc_python_out=services/user \
  protos/user/user.proto

# Order Service
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/order \
  --grpc_python_out=services/order \
  protos/order/order.proto \
  protos/product/product.proto

# Product Service
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/product \
  --grpc_python_out=services/product \
  protos/product/product.proto

# Gateway Service
uv run python -m grpc_tools.protoc -I protos \
  --python_out=services/gateway \
  --grpc_python_out=services/gateway \
  protos/user/user.proto \
  protos/order/order.proto \
  protos/product/product.proto