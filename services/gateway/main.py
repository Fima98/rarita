from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
import grpc

from product import product_pb2, product_pb2_grpc
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    product_host = os.getenv("PRODUCT_SERVICE_HOST", "localhost:50051")
    product_channel = grpc.insecure_channel(product_host)
    app.state.product = product_pb2_grpc.ProductServiceStub(product_channel)
    yield
    product_channel.close()


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
