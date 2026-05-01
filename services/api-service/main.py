"""
Product Catalog API Service.

A FastAPI application that provides CRUD operations for products.
Connects to a PostgreSQL database via SQLAlchemy and exposes
Prometheus metrics on the /metrics endpoint.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from database import Base, engine
from routers import products

# ---------------------------------------------------------------------------
# Prometheus metrics (defined at module level so they are registered exactly
# once and survive worker reloads without raising "Duplicated timeseries").
# ---------------------------------------------------------------------------
REQUEST_COUNTER = Counter(
    "api_http_requests_total",
    "Total number of HTTP requests handled by the api-service.",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "Latency of HTTP requests handled by the api-service in seconds.",
    ["method", "endpoint"],
)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Product Catalog API",
    version="1.0.0",
    description="CRUD API for the DevOps Capstone product catalog.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next: Callable) -> Response:
    """Capture metrics for every HTTP request."""
    start_time = time.perf_counter()
    method = request.method
    # Use the raw path so unknown routes are still recorded.
    endpoint = request.url.path

    response: Response = await call_next(request)

    duration = time.perf_counter() - start_time
    REQUEST_COUNTER.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(response.status_code),
    ).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
    return response


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on application startup."""
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness/readiness probe endpoint."""
    return {"status": "healthy", "service": "api-service", "version": "1.0.0"}


@app.get("/metrics", tags=["metrics"])
def metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
