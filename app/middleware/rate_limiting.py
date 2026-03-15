import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Dict, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# --- Storage Interface ---

class RateLimitStorage(ABC):
    @abstractmethod
    def increment(self, key: str, window: int) -> Tuple[int, float]:
        """
        Returns: (current_count, window_start_timestamp)
        """
        pass


# --- In-Memory Implementation ---

class InMemoryStorage(RateLimitStorage):
    def __init__(self):
        self._store: Dict[str, Tuple[datetime, int]] = defaultdict(
            lambda: (datetime.now(), 0)
        )

    def increment(self, key: str, window: int) -> Tuple[int, float]:
        now = datetime.now()
        last_reset, count = self._store[key]
        elapsed = (now - last_reset).total_seconds()

        if elapsed >= window:
            self._store[key] = (now, 1)
            return 1, now.timestamp()
        else:
            self._store[key] = (last_reset, count + 1)
            return count + 1, last_reset.timestamp()


# --- Middleware ---

EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}
EXEMPT_METHODS = {"OPTIONS"}

_instance: "RateLimiterMiddleware | None" = None

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, storage: RateLimitStorage):
        super().__init__(app)
        global _instance
        _instance = self
        self.storage = storage

    def get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "127.0.0.1"

    def get_rate_limit(self, path: str) -> Tuple[int, int]:
        """Returns: (max_requests, window_seconds)"""
        if path.startswith("/api/v1/auth"):
            return (20, 60)
        return (100, 60)

    async def dispatch(self, request: Request, call_next):
        if request.method in EXEMPT_METHODS:
            return await call_next(request)

        path = request.url.path

        if path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self.get_client_ip(request)
        max_requests, window = self.get_rate_limit(path)
        route_key = "auth" if path.startswith("/api/v1/auth") else "api"
        key = f"{client_ip}:{route_key}"

        count, window_start = self.storage.increment(key, window)

        if count > max_requests:
            elapsed = (datetime.now().timestamp() - window_start)
            retry_after = int(window - elapsed)
            logger.warning(f"Rate limit exceeded: {client_ip} on {path}")
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after_seconds": retry_after,
                }
            )

        return await call_next(request)



