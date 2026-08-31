from concurrent import futures
import grpc
from sqlmodel import SQLModel, select

from db import engine, get_session
from models import User
from user import user_pb2, user_pb2_grpc
import uuid
import os
import jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "secret-key")
ALGORITHM = "HS256"


class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    def CreateUser(self, request, context):
        with next(get_session()) as session:
            db_user = User(
                name=request.name,
                email=request.email,
                password=request.password,
            )
            session.add(db_user)
            session.commit()
            session.refresh(db_user)

            return user_pb2.UserResponse(
                id=str(db_user.id),
                name=db_user.name,
                email=db_user.email,
            )

    def LoginUser(self, request, context):
        with next(get_session()) as session:
            statement = select(User).where(User.email == request.email)
            user = session.exec(statement).first()

            if not user or user.password != request.password:
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Invalid email or password"
                )

            payload = {"sub": str(user.id)}
            token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

            return user_pb2.LoginResponse(
                access_token=token,
                token_type="bearer"
            )

    def GetUsers(self, request, context):
        with next(get_session()) as session:
            users = session.exec(select(User)).all()
            user_responses = [
                user_pb2.UserResponse(
                    id=str(u.id),
                    name=u.name,
                    email=u.email,
                )
                for u in users
            ]
            return user_pb2.UsersResponse(users=user_responses)

    def GetUser(self, request, context):
        with next(get_session()) as session:
            try:
                user_id = uuid.UUID(request.id)
            except ValueError:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              "Invalid UUID format")
            user = session.get(User, user_id)
            if not user:
                context.abort(grpc.StatusCode.NOT_FOUND, "User not found")

            return user_pb2.UserResponse(
                id=str(user.id),
                name=user.name,
                email=user.email,
            )


def serve():
    SQLModel.metadata.create_all(engine)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server)
    server.add_insecure_port("[::]:50052")
    print("User gRPC service running on port 50052...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
