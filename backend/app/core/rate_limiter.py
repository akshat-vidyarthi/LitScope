import time
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class SlidingWindowRateLimiter:
    """
    In-memory sliding window rate limiter.
    Zero external dependencies, light memory footprint, automatic window cleanup.
    """
    def __init__(self):
        # Key: (ip, route_tier) -> List[timestamps]
        self._requests: Dict[Tuple[str, str], List[float]] = {}
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self, current_time: float):
        """Purge entries older than 120 seconds every 60 seconds."""
        if current_time - self._last_cleanup < 60.0:
            return
        self._last_cleanup = current_time
        expired_keys = []
        for key, timestamps in self._requests.items():
            valid_ts = [t for t in timestamps if current_time - t < 120.0]
            if not valid_ts:
                expired_keys.append(key)
            else:
                self._requests[key] = valid_ts
        for k in expired_keys:
            del self._requests[k]

    def is_rate_limited(self, ip: str, tier: str, max_requests: int, window_seconds: float = 60.0) -> Tuple[bool, int]:
        """
        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        self._cleanup_old_entries(now)

        key = (ip, tier)
        timestamps = self._requests.get(key, [])
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]

        if len(valid_timestamps) >= max_requests:
            oldest_in_window = valid_timestamps[0]
            retry_after = max(1, int(window_seconds - (now - oldest_in_window)))
            self._requests[key] = valid_timestamps
            return True, retry_after

        valid_timestamps.append(now)
        self._requests[key] = valid_timestamps
        return False, 0


# Singleton rate limiter instance
limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware enforcing tiered endpoint rate limits.
    Inspects X-Forwarded-For header for reverse proxies (e.g. Render, Cloudflare).
    """
    async def dispatch(self, request: Request, call_next):
        # Exempt health check and docs
        path = request.url.path
        if path.startswith(("/docs", "/openapi.json", "/redoc", "/api/v1/health")):
            return await call_next(request)

        # Extract client IP, respecting reverse proxies
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # Determine rate limit tier
        # 1. Auth: 10 requests / minute
        if path.startswith(("/api/v1/auth/login", "/api/v1/auth/register")):
            tier, max_req = "auth", 10

        # 2. AI Synthesis & Extraction: 15 requests / minute
        elif any(path.endswith(s) for s in ("/ask", "/matrix/extract", "/gaps/generate", "/reviews/generate")):
            tier, max_req = "ai_synthesis", 15

        # 3. Discovery: 25 requests / minute
        elif path.startswith("/api/v1/discovery"):
            tier, max_req = "discovery", 25

        # 4. Upload: 10 uploads / minute
        elif path.startswith("/api/v1/papers/upload"):
            tier, max_req = "upload", 10

        # 5. Default general API: 120 requests / minute
        else:
            tier, max_req = "general", 120

        is_limited, retry_after = limiter.is_rate_limited(client_ip, tier, max_req)
        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded for {tier} operations. Please wait {retry_after} seconds before retrying.",
                    "retry_after": retry_after,
                    "tier": tier
                },
                headers={"Retry-After": str(retry_after)}
            )

        return await call_next(request)
