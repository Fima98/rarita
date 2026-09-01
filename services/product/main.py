import grpc
import re
from concurrent import futures
from product import product_pb2, product_pb2_grpc
from google.protobuf.struct_pb2 import Struct
from db import engine, get_session
from sqlmodel import SQLModel, select
from models import Product, Category, ProductVariant
import uuid
from google.protobuf.json_format import MessageToDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload


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
            reserved_stock=v.reserved_stock,
            is_active=v.is_active,
            images=v.images or [],
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
        variants=proto_variants,
        is_active=product.is_active,
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

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                context.abort(
                    grpc.StatusCode.ALREADY_EXISTS,
                    f"Category with slug '{slug}' already exists"
                )

            session.refresh(category)

            return product_pb2.CategoryResponse(
                id=str(category.id),
                name=category.name,
                slug=category.slug
            )

    def GetProduct(self, request, context):
        try:
            product_uuid = uuid.UUID(request.id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid product ID format")

        with next(get_session()) as session:
            product = session.get(Product, product_uuid)
            if not product:
                context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")

            if not getattr(product, "is_active", True):
                context.abort(grpc.StatusCode.NOT_FOUND,
                              "Product is no longer active")

            return db_to_proto(product)

    def ListProducts(self, request, context):
        limit = request.limit if request.limit > 0 else 100
        offset = request.offset if request.offset >= 0 else 0

        with next(get_session()) as session:
            statement = (
                select(Product)
                .where(Product.is_active == True)
                .options(
                    selectinload(Product.category),
                    selectinload(Product.variants),
                )
            )

            if request.HasField("category_id") and request.category_id:
                try:
                    cat_uuid = uuid.UUID(request.category_id)
                    statement = statement.where(
                        Product.category_id == cat_uuid)
                except ValueError:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "Invalid category_id UUID format",
                    )

            statement = statement.offset(offset).limit(limit)
            products = session.exec(statement).all()

            proto_products = [db_to_proto(p) for p in products]
            return product_pb2.ListProductsResponse(products=proto_products)

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
                    reserved_stock=0,
                    is_active=True,
                    images=list(v.images)
                )
                for v in request.variants
            ]

            attributes_dict = MessageToDict(request.attributes)

            db_product = Product(
                name=request.name,
                description=request.description,
                category_id=category_uuid,
                attributes=attributes_dict,
                is_active=True,
                variants=variants
            )

            session.add(db_product)
            session.commit()
            session.refresh(db_product)

            return db_to_proto(db_product)

    def CreateProductVariant(self, request, context):
        try:
            product_uuid = uuid.UUID(request.product_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid product ID format")

        if request.price <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Price must be greater than 0")

        if not request.sku.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "SKU cannot be empty")

        with next(get_session()) as session:
            product = session.get(Product, product_uuid)
            if not product:
                context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")

            variant = ProductVariant(
                product_id=product_uuid,
                sku=request.sku,
                color_name=request.color_name,
                color_hex=request.color_hex,
                price=request.price,
                stock=request.stock,
                reserved_stock=0,
                is_active=True,
                images=list(request.images)
            )

            session.add(variant)
            session.commit()
            session.refresh(variant)

            return product_pb2.ProductVariant(
                variant_id=str(variant.id),
                sku=variant.sku,
                color_name=variant.color_name,
                color_hex=variant.color_hex,
                price=variant.price,
                stock=variant.stock,
                reserved_stock=variant.reserved_stock,
                is_active=variant.is_active,
                images=variant.images or []
            )

    def UpdateProduct(self, request, context):
        try:
            product_uuid = uuid.UUID(request.id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid product ID")

        with next(get_session()) as session:
            product = session.get(Product, product_uuid)
            if not product:
                context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")

            if request.HasField("name"):
                product.name = request.name
            if request.HasField("description"):
                product.description = request.description
            if request.HasField("category_id"):
                product.category_id = uuid.UUID(request.category_id)
            if request.HasField("attributes"):
                product.attributes = MessageToDict(request.attributes)
            if request.HasField("is_active"):
                product.is_active = request.is_active

            session.add(product)
            session.commit()
            session.refresh(product)

            return db_to_proto(product)

    def UpdateProductVariant(self, request, context):
        try:
            variant_uuid = uuid.UUID(request.variant_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid variant ID")

        with next(get_session()) as session:
            variant = session.get(ProductVariant, variant_uuid)
            if not variant:
                context.abort(grpc.StatusCode.NOT_FOUND, "Variant not found")

            if request.HasField("price"):
                variant.price = request.price
            if request.HasField("stock"):
                variant.stock = request.stock
            if request.HasField("reserved_stock"):
                variant.reserved_stock = request.reserved_stock
            if request.HasField("is_active"):
                variant.is_active = request.is_active

            session.add(variant)
            session.commit()
            session.refresh(variant)

            return product_pb2.ProductVariant(
                variant_id=str(variant.id),
                sku=variant.sku,
                color_name=variant.color_name,
                color_hex=variant.color_hex,
                price=variant.price,
                stock=variant.stock,
                reserved_stock=variant.reserved_stock,
                is_active=variant.is_active,
                images=variant.images or []
            )

    def DeleteProduct(self, request, context):
        try:
            product_uuid = uuid.UUID(request.id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid product ID")

        with next(get_session()) as session:
            product = session.get(Product, product_uuid)
            if not product:
                context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")

            session.delete(product)
            session.commit()

            return product_pb2.DeleteProductResponse(success=True, message="Product deleted successfully")

    def DeleteProductVariant(self, request, context):
        try:
            variant_uuid = uuid.UUID(request.variant_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "Invalid variant ID")

        with next(get_session()) as session:
            variant = session.get(ProductVariant, variant_uuid)
            if not variant:
                context.abort(grpc.StatusCode.NOT_FOUND, "Variant not found")

            session.delete(variant)
            session.commit()

            return product_pb2.DeleteProductVariantResponse(success=True, message="Variant deleted successfully")


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
