from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.protobuf.json_format import MessageToDict
import grpc

from auth import get_current_user_id, get_optional_user_id
from order import order_pb2
from schema import CreateOrderSchema, ProcessPaymentSchema

router = APIRouter(tags=["Orders & Payments"])


@router.post("/orders/", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: CreateOrderSchema,
    request: Request,
    user_id: str | None = Depends(get_optional_user_id)
):
    items = [
        order_pb2.OrderItemInput(
            product_variant_id=item.product_variant_id,
            quantity=item.quantity
        )
        for item in payload.items
    ]
    customer = order_pb2.CustomerInfo(
        name=payload.customer.name,
        phone=payload.customer.phone,
        email=payload.customer.email
    )
    kwargs = {
        "items": items,
        "customer": customer,
        "shipping_address": payload.shipping_address
    }
    if user_id:
        kwargs["user_id"] = user_id

    grpc_request = order_pb2.CreateOrderRequest(**kwargs)

    try:
        response = request.app.state.order_stub.CreateOrder(grpc_request)
        return MessageToDict(response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.post("/payments/webhook")
def process_payment(payload: ProcessPaymentSchema, request: Request):
    grpc_request = order_pb2.PaymentWebhookRequest(
        order_id=payload.order_id,
        is_success=payload.is_success
    )

    try:
        response = request.app.state.order_stub.ProcessPayment(grpc_request)
        return MessageToDict(response, preserving_proto_field_name=True)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")


@router.get("/orders/my")
def get_my_orders(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    try:
        grpc_req = order_pb2.GetUserOrdersRequest(user_id=user_id)
        response = request.app.state.order_stub.GetUserOrders(grpc_req)
        result = MessageToDict(response, preserving_proto_field_name=True)
        return {"orders": result.get("orders", [])}
    except grpc.RpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")
