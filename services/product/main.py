import grpc
from concurrent import futures
from product import product_pb2, product_pb2_grpc
from google.protobuf.struct_pb2 import Struct


class ProductService(product_pb2_grpc.ProductServiceServicer):
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


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductServiceServicer_to_server(
        ProductService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
