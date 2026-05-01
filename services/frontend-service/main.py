"""
Frontend Service.

A FastAPI + Jinja2 web UI that talks to the api-service and auth-service.
Renders Bootstrap pages for the catalog browser, login, and registration.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import FastAPI, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    generate_latest,
)

API_SERVICE_URL = os.getenv("API_SERVICE_URL", "http://api-service:8000")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5.0"))

FRONTEND_REQUESTS = Counter(
    "frontend_requests_total",
    "Total number of HTTP requests handled by the frontend-service.",
    ["endpoint", "status"],
)

app = FastAPI(
    title="Frontend Service",
    version="1.0.0",
    description="Server-rendered UI for the DevOps Capstone product catalog.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="./templates")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    FRONTEND_REQUESTS.labels(
        endpoint=request.url.path,
        status=str(response.status_code),
    ).inc()
    return response


def _is_logged_in(request: Request) -> bool:
    return bool(request.cookies.get("access_token"))


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Response:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Product Catalog",
            "logged_in": _is_logged_in(request),
        },
    )


@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request) -> Response:
    products: list = []
    error: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(f"{API_SERVICE_URL}/products/")
            resp.raise_for_status()
            products = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        error = f"Could not load products: {exc}"

    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "title": "Products",
            "products": products,
            "error": error,
            "logged_in": _is_logged_in(request),
        },
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Login",
            "error": None,
            "logged_in": _is_logged_in(request),
        },
    )


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
) -> Response:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/login",
                json={"email": email, "password": password},
            )
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            redirect = RedirectResponse(url="/products", status_code=303)
            redirect.set_cookie(
                key="access_token",
                value=token,
                httponly=True,
                samesite="lax",
                max_age=60 * 30,
            )
            return redirect
    except httpx.HTTPError:
        pass

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Login",
            "error": "Invalid credentials",
            "logged_in": False,
        },
        status_code=401,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> Response:
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Register",
            "error": None,
            "logged_in": _is_logged_in(request),
        },
    )


@app.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
) -> Response:
    error: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "full_name": full_name or None,
                },
            )
        if resp.status_code in (200, 201):
            return RedirectResponse(url="/login", status_code=303)
        try:
            error = resp.json().get("detail") or "Registration failed"
        except ValueError:
            error = "Registration failed"
    except httpx.HTTPError as exc:
        error = f"Could not reach auth service: {exc}"

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Register",
            "error": error,
            "logged_in": False,
        },
        status_code=400,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@app.get("/logout")
async def logout() -> Response:
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie("access_token")
    return redirect


# ---------------------------------------------------------------------------
# Health and metrics
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "frontend-service"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
