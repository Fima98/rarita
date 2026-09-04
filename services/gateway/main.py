import os
from contextlib import asynccontextmanager

import grpc
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from order import order_pb2_grpc
from product import product_pb2_grpc
from user import user_pb2_grpc

from routers import orders, products, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PRODUCT
    product_host = os.getenv("PRODUCT_SERVICE_HOST", "localhost:50051")
    product_channel = grpc.insecure_channel(product_host)
    app.state.product = product_pb2_grpc.ProductServiceStub(product_channel)

    # USER
    user_host = os.getenv("USER_SERVICE_HOST", "localhost:50052")
    user_channel = grpc.insecure_channel(user_host)
    app.state.user_stub = user_pb2_grpc.UserServiceStub(user_channel)

    # ORDER
    order_host = os.getenv("ORDER_SERVICE_HOST", "localhost:50053")
    order_channel = grpc.insecure_channel(order_host)
    app.state.order_stub = order_pb2_grpc.OrderServiceStub(order_channel)

    yield

    product_channel.close()
    user_channel.close()
    order_channel.close()


api_key_header = APIKeyHeader(name="X-Internal-Secret", auto_error=False)

app = FastAPI(
    title="API Gateway",
    lifespan=lifespan,
    dependencies=[Depends(api_key_header)]
)

EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def verify_internal_secret(request: Request, call_next):
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    client_secret = request.headers.get("X-Internal-Secret")
    if client_secret != os.getenv("INTERNAL_API_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    return await call_next(request)


# СONNECT ROUTERS
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
