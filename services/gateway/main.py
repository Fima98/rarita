from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
import grpc

from product import product_pb2, product_pb2_grpc
from user import user_pb2, user_pb2_grpc
import os
from schema import UserCreate


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
    yield
    product_channel.close()
    user_channel.close()


app = FastAPI(title="API Gateway", lifespan=lifespan)


@app.get("/products/{product_id}")
async def get_product(product_id: int, request: Request):
    try:
        grpc_req = product_pb2.ProductRequest(id=product_id)
        response = request.app.state.product.GetProduct(grpc_req)

        return {
            "id": response.id,
            "name": response.name,
            "description": response.description,
            "price": response.price,
            "stock": response.stock,
            "category_id": response.category_id,
            "category_name": response.category_name,
            "attributes": dict(response.attributes),
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}"
        )


@app.post("/users/")
def create_user(user: UserCreate):
    try:
        response = app.state.user_stub.CreateUser(
            user_pb2.CreateUserRequest(
                name=user.name,
                email=user.email,
                password=user.password,
            )
        )
        return {"id": response.id, "name": response.name, "email": response.email}
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=e.details())


@app.get("/users/")
def get_users():
    try:
        response = app.state.user_stub.GetUsers(user_pb2.GetUsersRequest())
        return [
            {"id": u.id, "name": u.name, "email": u.email}
            for u in response.users
        ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=e.details())


@app.get("/users/{user_id}")
def get_user(user_id: str):
    try:
        response = app.state.user_stub.GetUser(
            user_pb2.GetUserRequest(id=user_id))
        return {
            "id": response.id,
            "name": response.name,
            "email": response.email
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(
                status_code=400, detail="Invalid user ID format")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}"
        )
