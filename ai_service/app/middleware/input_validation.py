from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

# Limits
MAX_MESSAGE_LENGTH = 5000  # characters
MAX_IMAGES_PER_REQUEST = 5
MAX_IMAGE_SIZE_B64 = 15_000_000  # ~10MB in base64 encoding
MAX_BODY_SIZE = 20_000_000  # 20MB total request body


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validates request body size and content limits."""

    async def dispatch(self, request: Request, call_next):
        # Only validate POST requests to our API endpoints
        if request.method == "POST" and request.url.path in ("/chat/", "/chat", "/clinical-advice/", "/clinical-advice"):
            # Check content-length header
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "status": "error",
                        "response": "O pedido é demasiado grande. Tenta com menos imagens ou imagens mais pequenas.",
                    },
                )

        return await call_next(request)
