from contextlib import asynccontextmanager
import os
import grpc
from fastapi import FastAPI, HTTPException, Request, status
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct

from product import product_pb2, product_pb2_grpc
from schema import ProductCreateSchema, UserCreate, CategoryCreateSchema
from user import user_pb2, user_pb2_grpc


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


@app.post("/users/", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, request: Request):
    try:
        response = request.app.state.user_stub.CreateUser(
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
def get_users(request: Request):
    try:
        response = request.app.state.user_stub.GetUsers(
            user_pb2.GetUsersRequest())
        return [
            {"id": u.id, "name": u.name, "email": u.email}
            for u in response.users
        ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=e.details())


@app.get("/users/{user_id}")
def get_user(user_id: str, request: Request):
    try:
        response = request.app.state.user_stub.GetUser(
            user_pb2.GetUserRequest(id=user_id)
        )
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
                status_code=400, detail="Invalid user ID format"
            )
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}"
        )


@app.post("/products/", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreateSchema, request: Request):
    attrs_struct = Struct()
    attrs_struct.update(payload.attributes)

    grpc_variants = [
        product_pb2.CreateProductVariantInput(
            sku=v.sku,
            color_name=v.color_name,
            color_hex=v.color_hex,
            price=v.price,
            stock=v.stock,
            images=v.images
        )
        for v in payload.variants
    ]

    grpc_request = product_pb2.CreateProductRequest(
        name=payload.name,
        description=payload.description,
        category_id=str(payload.category_id),
        attributes=attrs_struct,
        variants=grpc_variants
    )

    try:
        grpc_response = request.app.state.product.CreateProduct(grpc_request)
    except grpc.RpcError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if e.code() == grpc.StatusCode.NOT_FOUND:
            status_code = status.HTTP_404_NOT_FOUND

        raise HTTPException(status_code=status_code, detail=e.details())

    return MessageToDict(
        grpc_response,
        preserving_proto_field_name=True
    )


@app.get("/products/{product_id}")
def get_product(product_id: str, request: Request):
    try:
        grpc_req = product_pb2.ProductRequest(id=product_id)
        response = request.app.state.product.GetProduct(grpc_req)
        return MessageToDict(response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}"
        )


@app.get("/products/")
def list_products(
    request: Request,
    limit: int = 10,
    offset: int = 0,
    category_id: str | None = None
):
    try:
        grpc_req = product_pb2.ListProductsRequest(
            limit=limit,
            offset=offset,
            category_id=category_id if category_id else None
        )
        response = request.app.state.product.ListProducts(grpc_req)
        result = MessageToDict(response, preserving_proto_field_name=True)
        return result.get("products", [])
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}"
        )


@app.post("/categories/", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreateSchema, request: Request):
    try:
        grpc_request = product_pb2.CreateCategoryRequest(name=payload.name)
        grpc_response = request.app.state.product.CreateCategory(grpc_request)
        return MessageToDict(grpc_response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=e.details())
