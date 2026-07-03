import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .metrics import METRICS

log = logging.getLogger("careloop.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs one structured line per request and feeds the metrics reservoir."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            METRICS.incr("http_requests_5xx_total")
            log.exception(
                "unhandled error",
                extra={
                    "ctx": {
                        "request_id": request_id,
                        "http": {"method": request.method, "path": request.url.path},
                        "duration_ms": round(duration_ms, 1),
                    }
                },
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        route = f"{request.method} {request.url.path}"
        METRICS.incr("http_requests_total")
        if response.status_code >= 500:
            METRICS.incr("http_requests_5xx_total")
        METRICS.observe_latency(route, duration_ms)
        log.info(
            "request",
            extra={
                "ctx": {
                    "request_id": request_id,
                    "http": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    },
                    "duration_ms": round(duration_ms, 1),
                }
            },
        )
        response.headers["x-request-id"] = request_id
        return response
