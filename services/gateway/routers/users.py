from fastapi import APIRouter, HTTPException, Request, status
import grpc
from user import user_pb2
from schema import UserCreate, LoginSchema

router = APIRouter(tags=["Users"])


@router.post("/signup/", status_code=status.HTTP_201_CREATED)
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


@router.post("/login/")
def login(payload: LoginSchema, request: Request):
    try:
        response = request.app.state.user_stub.LoginUser(
            user_pb2.LoginRequest(
                email=payload.email,
                password=payload.password
            )
        )
        return {
            "access_token": response.access_token,
            "token_type": response.token_type
        }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.UNAUTHENTICATED:
            raise HTTPException(status_code=401, detail=e.details())
        raise HTTPException(status_code=500, detail=e.details())


@router.get("/users/")
def get_users(request: Request):
    try:
        response = request.app.state.user_stub.GetUsers(
            user_pb2.GetUsersRequest())
        return [{"id": u.id, "name": u.name, "email": u.email} for u in response.users]
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=e.details())


@router.get("/users/{user_id}")
def get_user(user_id: str, request: Request):
    try:
        response = request.app.state.user_stub.GetUser(
            user_pb2.GetUserRequest(id=user_id)
        )
        return {"id": response.id, "name": response.name, "email": response.email}
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="User not found")
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(
                status_code=400, detail="Invalid user ID format")
        raise HTTPException(
            status_code=500, detail=f"gRPC service error: {e.details()}")
