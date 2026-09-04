from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
import grpc

from auth import get_current_user_id
from product import product_pb2
from schema import (
    CategoryCreateSchema,
    ProductCreateSchema,
    ProductUpdateSchema,
    ProductVariantCreateSchema,
    ProductVariantUpdateSchema,
)

router = APIRouter(tags=["Products & Categories"])


@router.post("/products/", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateSchema,
    request: Request,
    _: str = Depends(get_current_user_id)
):
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

    return MessageToDict(grpc_response, preserving_proto_field_name=True)


@router.get("/products/{product_id}")
def get_product(product_id: str, request: Request):
    try:
        grpc_req = product_pb2.ProductRequest(id=product_id)
        response = request.app.state.product.GetProduct(grpc_req)
        return MessageToDict(response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.get("/products/")
def list_products(
    request: Request,
    limit: int = 10,
    offset: int = 0,
    category_id: str | None = None
):
    try:
        kwargs = {"limit": limit, "offset": offset}
        if category_id:
            kwargs["category_id"] = category_id
        grpc_req = product_pb2.ListProductsRequest(**kwargs)
        response = request.app.state.product.ListProducts(grpc_req)
        result = MessageToDict(response, preserving_proto_field_name=True)
        return result.get("products", [])
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.post("/products/{product_id}/variants", status_code=status.HTTP_201_CREATED)
def create_product_variant(
    product_id: str,
    payload: ProductVariantCreateSchema,
    request: Request,
    _: str = Depends(get_current_user_id),
):
    grpc_request = product_pb2.CreateProductVariantRequest(
        product_id=product_id,
        sku=payload.sku,
        color_name=payload.color_name,
        color_hex=payload.color_hex,
        price=payload.price,
        stock=payload.stock,
        images=payload.images,
    )

    try:
        grpc_response = request.app.state.product.CreateProductVariant(
            grpc_request)
        return MessageToDict(grpc_response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.post("/categories/", status_code=status.HTTP_201_CREATED)
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


@router.put("/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductUpdateSchema,
    request: Request,
    _: str = Depends(get_current_user_id)
):
    kwargs = {"id": product_id}
    if payload.name is not None:
        kwargs["name"] = payload.name
    if payload.description is not None:
        kwargs["description"] = payload.description
    if payload.category_id is not None:
        kwargs["category_id"] = str(payload.category_id)
    if payload.is_active is not None:
        kwargs["is_active"] = payload.is_active
    if payload.attributes is not None:
        attrs_struct = Struct()
        attrs_struct.update(payload.attributes)
        kwargs["attributes"] = attrs_struct

    grpc_request = product_pb2.UpdateProductRequest(**kwargs)

    try:
        grpc_response = request.app.state.product.UpdateProduct(grpc_request)
        return MessageToDict(grpc_response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.put("/variants/{variant_id}")
def update_product_variant(
    variant_id: str,
    payload: ProductVariantUpdateSchema,
    request: Request,
    _: str = Depends(get_current_user_id)
):
    kwargs = {"variant_id": variant_id}
    if payload.price is not None:
        kwargs["price"] = payload.price
    if payload.stock_delta is not None:
        kwargs["stock_delta"] = payload.stock_delta
    if payload.reserved_stock_delta is not None:
        kwargs["reserved_stock_delta"] = payload.reserved_stock_delta
    if payload.is_active is not None:
        kwargs["is_active"] = payload.is_active

    grpc_request = product_pb2.UpdateProductVariantRequest(**kwargs)

    try:
        grpc_response = request.app.state.product.UpdateProductVariant(
            grpc_request)
        return MessageToDict(grpc_response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Variant not found")
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(
    product_id: str,
    request: Request,
    _: str = Depends(get_current_user_id)
):
    try:
        grpc_req = product_pb2.DeleteProductRequest(id=product_id)
        response = request.app.state.product.DeleteProduct(grpc_req)
        return {"success": response.success, "message": response.message}
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.delete("/variants/{variant_id}", status_code=status.HTTP_200_OK)
def delete_product_variant(
    variant_id: str,
    request: Request,
    _: str = Depends(get_current_user_id)
):
    try:
        grpc_req = product_pb2.DeleteProductVariantRequest(
            variant_id=variant_id)
        response = request.app.state.product.DeleteProductVariant(grpc_req)
        return {"success": response.success, "message": response.message}
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Variant not found")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")
