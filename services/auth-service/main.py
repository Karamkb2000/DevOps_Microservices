"""
Auth Service.

A FastAPI application that handles user registration, JWT login, and token
verification. Connects to a PostgreSQL database via SQLAlchemy and exposes
Prometheus metrics on the /metrics endpoint.
"""
from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    generate_latest,
)

from database import Base, engine
from routers import users

# ---------------------------------------------------------------------------
# Module-level Prometheus metrics
# ---------------------------------------------------------------------------
AUTH_REQUESTS = Counter(
    "auth_requests_total",
    "Total number of authentication-related HTTP requests.",
    ["endpoint", "status"],
)


app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    description="JWT-based authentication service for the DevOps Capstone.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/auth", tags=["auth"])


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """Increment the auth_requests_total counter on every HTTP request."""
    response: Response = await call_next(request)
    AUTH_REQUESTS.labels(
        endpoint=request.url.path,
        status=str(response.status_code),
    ).inc()
    return response


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on application startup."""
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness/readiness probe endpoint."""
    return {"status": "healthy", "service": "auth-service"}


@app.get("/metrics", tags=["metrics"])
def metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
