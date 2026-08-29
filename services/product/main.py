import grpc
import re
from concurrent import futures
from product import product_pb2, product_pb2_grpc
from google.protobuf.struct_pb2 import Struct
from db import engine, get_session
from sqlmodel import SQLModel, select
from models import Product, Category, ProductVariant
import uuid


def generate_slug(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[-\s]+", "-", slug)


def db_to_proto(product: Product) -> product_pb2.ProductResponse:
    attrs = Struct()
    if product.attributes:
        attrs.update(product.attributes)

    proto_variants = [
        product_pb2.ProductVariant(
            variant_id=str(v.id),
            sku=v.sku,
            color_name=v.color_name,
            color_hex=v.color_hex,
            price=v.price,
            stock=v.stock,
            images=v.images or []
        )
        for v in product.variants
    ]

    return product_pb2.ProductResponse(
        id=str(product.id),
        name=product.name,
        description=product.description,
        category_id=str(product.category_id),
        category_name=product.category.name if product.category else "",
        attributes=attrs,
        variants=proto_variants
    )


class ProductService(product_pb2_grpc.ProductServiceServicer):
    def CreateCategory(self, request, context):
        name = request.name.strip()
        if not name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Category name cannot be empty")

        slug = generate_slug(name)

        with next(get_session()) as session:
            category = Category(name=name, slug=slug)
            session.add(category)
            session.commit()
            session.refresh(category)

            return product_pb2.CategoryResponse(
                id=str(category.id),
                name=category.name,
                slug=category.slug
            )

    def GetProduct(self, request, context):
        attrs = Struct()
        attrs.update({
            "color": "silver",
            "battery_type": "AA",
            "has_remote": True
        })

        return product_pb2.ProductResponse(
            id=request.id,
            name="Sony Walkman WM EX-655",
            description="Vintage cassette player with remote",
            price=150.0,
            stock=1,
            category_id=10,
            category_name="Audio",
            attributes=attrs
        )

    def ListProducts(self, request, context):
        pass

    def CreateProduct(self, request, context):
        if not request.name.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Product name cannot be empty")

        if not request.variants:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Product must have at least one variant")

        for v in request.variants:
            if v.price <= 0:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              f"Price for SKU '{v.sku}' must be greater than 0")
            if not v.sku.strip():
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              "SKU cannot be empty")

        try:
            category_uuid = uuid.UUID(request.category_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid category_id UUID format")

        with next(get_session()) as session:
            variants = [
                ProductVariant(
                    sku=v.sku,
                    color_name=v.color_name,
                    color_hex=v.color_hex,
                    price=v.price,
                    stock=v.stock,
                    images=list(v.images)
                )
                for v in request.variants
            ]

            db_product = Product(
                name=request.name,
                description=request.description,
                category_id=uuid.UUID(request.category_id),
                attributes=dict(request.attributes),
                variants=variants
            )

            session.add(db_product)
            session.commit()
            session.refresh(db_product)

            return db_to_proto(db_product)


def serve():
    SQLModel.metadata.create_all(engine)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductServiceServicer_to_server(
        ProductService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
