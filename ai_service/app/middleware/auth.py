import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

# Routes that don't require API key authentication
PUBLIC_ROUTES = ["/", "/docs", "/openapi.json", "/redoc"]

API_SERVICE_KEY = os.getenv("AI_SERVICE_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates X-API-Key header against AI_SERVICE_KEY env var."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public routes
        if request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        # Skip auth if no key is configured (development mode)
        if not API_SERVICE_KEY:
            logger.warning("AI_SERVICE_KEY not configured - running without authentication")
            return await call_next(request)

        # Validate API key from header
        api_key = request.headers.get("X-API-Key", "")

        if not api_key:
            logger.warning(f"Request without API key from {request.client.host}: {request.url.path}")
            raise HTTPException(status_code=401, detail="API key required")

        if api_key != API_SERVICE_KEY:
            logger.warning(f"Invalid API key from {request.client.host}: {request.url.path}")
            raise HTTPException(status_code=401, detail="Invalid API key")

        return await call_next(request)
