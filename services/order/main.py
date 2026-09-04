import asyncio
import json
import os
import uuid
from datetime import datetime
import grpc
import aio_pika
from sqlmodel import Session, select

from order import order_pb2, order_pb2_grpc
from product import product_pb2, product_pb2_grpc
from db import engine
from models import Order, OrderItem, SQLModel

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "product:50051")
PORT = os.getenv("PORT", "50053")

SQLModel.metadata.create_all(engine)


# ==========================================
# Persistent gRPC Client for Product Service
# ==========================================
class ProductServiceClient:
    def __init__(self, target: str):
        self.target = target
        self.channel = None
        self.stub = None

    def connect(self):
        self.channel = grpc.aio.insecure_channel(self.target)
        self.stub = product_pb2_grpc.ProductServiceStub(self.channel)

    async def close(self):
        if self.channel:
            await self.channel.close()

    async def update_product_variant(
        self,
        variant_id: str,
        reserved_stock_delta: int = 0,
        stock_delta: int = 0
    ) -> product_pb2.ProductVariant:
        req = product_pb2.UpdateProductVariantRequest(
            variant_id=variant_id,
            reserved_stock_delta=reserved_stock_delta,
            stock_delta=stock_delta
        )
        return await self.stub.UpdateProductVariant(req)


product_client = ProductServiceClient(PRODUCT_SERVICE_URL)


# ==========================================
# RabbitMQ Consumers
# ==========================================
async def handle_dead_letter(message: aio_pika.IncomingMessage):
    async with message.process():
        print(
            f"[DLQ] Повідомлення остаточно не оброблено: {message.body.decode()}")


async def handle_order_timeout(message: aio_pika.IncomingMessage):
    headers = message.headers or {}
    deaths = headers.get("x-death", [])
    retries = sum(d["count"] for d in deaths) if deaths else 0

    if retries >= MAX_RETRIES:
        print(
            f"Order {message.body} failed after {MAX_RETRIES} retries. Sent to DLQ.")
        await message.reject(requeue=False)
        return
    try:

        data = json.loads(message.body.decode())
        order_uuid = uuid.UUID(data["order_id"])

        with Session(engine, expire_on_commit=False) as session:
            order = session.get(Order, order_uuid)
            if not order or order.status != "PENDING":
                return await message.ack()

            items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order_uuid)
            ).all()

            for item in items:
                await product_client.update_product_variant(
                    item.product_variant_id,
                    reserved_stock_delta=-item.quantity
                )

            order.status = "CANCELLED"
            session.add(order)
            session.commit()
        await message.ack()

    except Exception as e:
        print(f"[Error] Processing error: {e}. Redirecting to retry queue...")
        await message.channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=message.headers,
                delivery_mode=message.delivery_mode,
            ),
            routing_key="order_retry_queue",
        )
        await message.ack()


EXCHANGES_CONFIG = {
    "order_events": aio_pika.ExchangeType.TOPIC,
    "order_dlx": aio_pika.ExchangeType.TOPIC,
}

EVENT_HANDLERS = [
    ("order_events", "order.timeout", "order_timeout_queue", handle_order_timeout, {
        "x-dead-letter-exchange": "order_dlx",
        "x-dead-letter-routing-key": "order.dlq",
    }),
    (
        "order_dlx",
        "order.dlq",
        "order_dead_letter_queue",
        handle_dead_letter,
        None,
    ),
    # EXCHANGE NAME - ROUTING KEY - QUEUE NAME - HANDLER
]

MAX_RETRIES = 3  # for senging message to dead letter queue.


async def start_rabbitmq():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    await channel.set_qos(prefetch_count=10)

    exchanges = {}
    for name, ex_type in EXCHANGES_CONFIG.items():
        exchanges[name] = await channel.declare_exchange(name, ex_type)

    args = {
        "x-dead-letter-exchange": "order_events",
        "x-dead-letter-routing-key": "order.timeout",
        "x-message-ttl": 900000,  # 15 minutes
    }
    await channel.declare_queue("order_ttl_queue", durable=True, arguments=args)

    args_retry = {
        "x-dead-letter-exchange": "order_events",
        "x-dead-letter-routing-key": "order.timeout",
        "x-message-ttl": 60000,  # 1 minute
    }
    await channel.declare_queue("order_retry_queue", durable=True, arguments=args_retry)

    for ex_name, routing_key, queue_name, handler, queue_args in EVENT_HANDLERS:
        exchange = exchanges[ex_name]
        queue = await channel.declare_queue(queue_name, durable=True, arguments=queue_args)
        await queue.bind(exchange, routing_key=routing_key)
        await queue.consume(handler)

    return connection, channel, exchanges

# ==========================================
# Order Service Servicer
# ==========================================


class OrderServicer(order_pb2_grpc.OrderServiceServicer):
    def __init__(self, rabbit_channel, exchanges):
        self.rabbit_channel = rabbit_channel
        self.exchanges = exchanges

    async def CreateOrder(self, request, context):
        reserved_items = []
        total_price = 0.0

        try:
            for item in request.items:
                variant = await product_client.update_product_variant(
                    variant_id=item.product_variant_id,
                    reserved_stock_delta=item.quantity
                )
                unit_price = variant.price
                total_price += unit_price * item.quantity

                reserved_items.append({
                    "product_variant_id": item.product_variant_id,
                    "quantity": item.quantity,
                    "unit_price": unit_price
                })
        except grpc.RpcError as e:
            for res in reserved_items:
                await product_client.update_product_variant(
                    variant_id=res["product_variant_id"],
                    reserved_stock_delta=-res["quantity"]
                )
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation error: {e.details()}"
            )

        with Session(engine, expire_on_commit=False) as session:
            user_id = uuid.UUID(request.user_id) if request.user_id else None
            order = Order(
                user_id=user_id,
                total_price=total_price,
                customer_name=request.customer.name,
                customer_phone=request.customer.phone,
                customer_email=request.customer.email,
                shipping_address=request.shipping_address
            )
            session.add(order)
            session.commit()
            session.refresh(order)

            for res in reserved_items:
                db_item = OrderItem(
                    order_id=order.id,
                    product_variant_id=res["product_variant_id"],
                    quantity=res["quantity"],
                    price=res["unit_price"]
                )
                session.add(db_item)
            session.commit()

        await self.rabbit_channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"order_id": str(order.id)}).encode()
            ),
            routing_key="order_ttl_queue"
        )

        response_items = [
            order_pb2.OrderItemResponse(
                product_variant_id=res["product_variant_id"],
                quantity=res["quantity"],
                unit_price=res["unit_price"]
            )
            for res in reserved_items
        ]

        customer_info = order_pb2.CustomerInfo(
            name=order.customer_name,
            phone=order.customer_phone,
            email=order.customer_email
        )

        response_kwargs = {
            "order_id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "customer": customer_info,
            "shipping_address": order.shipping_address,
            "items": response_items,
            "created_at": order.created_at.isoformat(),
            "payment_url": f"https://pay.example.com/checkout/{order.id}",
        }
        if order.user_id:
            response_kwargs["user_id"] = str(order.user_id)

        return order_pb2.OrderResponse(**response_kwargs)

    async def ProcessPayment(self, request, context):
        try:
            order_uuid = uuid.UUID(request.order_id)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Invalid order_id format"
            )

        with Session(engine, expire_on_commit=False) as session:
            order = session.get(Order, order_uuid)
            if not order or order.status != "PENDING":
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    "Order not found or already processed"
                )

            items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()

            if request.is_success:
                order.status = "PAID"
                for item in items:
                    await product_client.update_product_variant(
                        variant_id=item.product_variant_id,
                        reserved_stock_delta=-item.quantity,
                        stock_delta=-item.quantity
                    )
                routing_key = "order.paid"
            else:
                order.status = "CANCELLED"
                for item in items:
                    await product_client.update_product_variant(
                        variant_id=item.product_variant_id,
                        reserved_stock_delta=-item.quantity
                    )
                routing_key = "order.cancelled"

            session.add(order)
            session.commit()

        await self.exchanges["order_events"].publish(
            aio_pika.Message(body=json.dumps(
                {"order_id": str(order.id)}).encode()),
            routing_key=routing_key
        )
        return order_pb2.PaymentWebhookResponse(success=True)

    async def GetUserOrders(self, request, context):
        with Session(engine, expire_on_commit=False) as session:
            user_uuid = uuid.UUID(request.user_id) if request.user_id else None
            orders = session.exec(select(Order).where(
                Order.user_id == user_uuid)).all()

            response_orders = []

            for order in orders:
                items = session.exec(
                    select(OrderItem).where(OrderItem.order_id == order.id)
                ).all()

                response_items = [
                    order_pb2.OrderItemResponse(
                        product_variant_id=item.product_variant_id,
                        quantity=item.quantity,
                        unit_price=item.price
                    )
                    for item in items
                ]

                customer_info = order_pb2.CustomerInfo(
                    name=order.customer_name,
                    phone=order.customer_phone,
                    email=order.customer_email
                )

                response_kwargs = {
                    "order_id": str(order.id),
                    "status": order.status,
                    "total_price": order.total_price,
                    "customer": customer_info,
                    "shipping_address": order.shipping_address,
                    "items": response_items,
                    "created_at": order.created_at.isoformat(),
                }
                if order.user_id:
                    response_kwargs["user_id"] = str(order.user_id)
                if order.status == "PENDING":
                    response_kwargs[
                        "payment_url"] = f"https://pay.example.com/checkout/{order.id}"

                response_orders.append(
                    order_pb2.OrderResponse(**response_kwargs)
                )

            return order_pb2.GetUserOrdersResponse(orders=response_orders)


async def serve():
    product_client.connect()
    connection, rabbit_channel, exchanges = await start_rabbitmq()

    server = grpc.aio.server()
    order_pb2_grpc.add_OrderServiceServicer_to_server(
        OrderServicer(rabbit_channel, exchanges), server
    )
    server.add_insecure_port(f"[::]:{PORT}")

    print(f"Order Service is running on port {PORT}...")
    await server.start()

    try:
        await server.wait_for_termination()
    finally:
        await product_client.close()
        await connection.close()


if __name__ == "__main__":
    asyncio.run(serve())
