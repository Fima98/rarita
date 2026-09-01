# Microservices E-Commerce API

A mini-project for learning microservices architecture, gRPC communication, and asynchronous interaction.

## Architecture

```text
[ Client ]
    │
    ▼ (HTTP / REST:80)
┌─────────────────────────────────────────┐
│                 Traefik                 │
│             (Reverse Proxy)             │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│              API Gateway                │
│ (FastAPI, JWT Auth, Internal API Secret)│
└───────────────────┬─────────────────────┘
                    │
                    ├─────── (gRPC) ───────┐
                    ▼                      ▼
           ┌─────────────────┐    ┌────────────────────┐
           │  User Service   │    │  Product Service   │
           │(gRPC, Argon2)   │    │(gRPC, Categories)  │
           └────────┬────────┘    └─────────┬──────────┘
                    ▼                       ▼
            [ PostgreSQL ]          [ PostgreSQL ]
             (rarita_user)         (rarita_product)
```

## Tech Stack

- **Reverse Proxy:** Traefik v3
- **API Gateway:** FastAPI, PyJWT, Pydantic v2
- **Microservices:** gRPC, Protocol Buffers
- **Databases & ORM:** PostgreSQL, SQLModel
- **Security:** Argon2 (`pwdlib`) for password hashing, JWT (30 days) for sessions
- **Containerization & Tooling:** Docker, Docker Compose, `uv`

## Quick Start

### 1. Environment Variables Setup

Create a `.env` file in the project root:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

PRODUCT_DB_NAME=rarita_product
USER_DB_NAME=rarita_user

INTERNAL_API_SECRET=super_secret_key_12345
JWT_SECRET_KEY=your_jwt_secret_key

```

### 2. Run Containers

```bash
docker compose up -d --build

```

API Documentation (Swagger) after startup: `http://localhost/docs`

## Implemented Services & Endpoints

### Gateway (REST API)

- `POST /signup/` — User registration (gRPC -> User Service)
- `POST /login/` — Authentication and JWT issuance (gRPC -> User Service)
- `GET /users/{user_id}` — Profile retrieval (gRPC -> User Service)
- `POST /products/` — Product creation with variants and attributes (gRPC -> Product Service)
- `GET /products/` — Product catalog with pagination (gRPC -> Product Service)
- `POST /categories/` — Category creation (gRPC -> Product Service)

## Plans

- [ ] Create `Order Service` and background task processing
- [ ] Add RabbitMQ for event-driven architecture (EDA) scenarios
- [ ] Configure orchestration in Kubernetes (Minikube / Helm)
