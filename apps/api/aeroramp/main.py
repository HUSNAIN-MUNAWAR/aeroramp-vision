from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from aeroramp.api.router import router
from aeroramp.core.config import get_settings
from aeroramp.core.logging import configure_logging
from aeroramp.db.base import Base
from aeroramp.db.session import engine

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment in {"development", "test"}:
        Base.metadata.create_all(bind=engine)
    yield

REQUEST_COUNT = Counter("aeroramp_http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("aeroramp_http_request_seconds", "HTTP request latency", ["method", "path"])


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id", f"req_{uuid.uuid4().hex[:16]}")
        request.state.request_id = request_id
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        queue = self.requests[client]
        while queue and now - queue[0] > 60:
            queue.popleft()
        if len(queue) >= settings.request_rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "Too many requests", "request_id": request_id}})
        queue.append(now)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'"
        route = request.url.path
        REQUEST_COUNT.labels(request.method, route, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
        return response


app = FastAPI(
    title="AeroRamp Vision API",
    version="0.1.0",
    description="Operational decision-support and analytics platform for airport turnaround and ramp-safety review.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors(), "request_id": getattr(request.state, "request_id", "unknown")}})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": str(exc) if settings.environment == "development" else "Unexpected server error", "request_id": getattr(request.state, "request_id", "unknown")}})


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready", "database": "available"})
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable", "detail": str(exc)})


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
