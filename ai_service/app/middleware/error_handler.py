from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.utils.php_api_client import PHPApiError


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler that catches unhandled exceptions
    and returns clean JSON responses without exposing internals."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except PHPApiError as e:
            logger.error(f"PHP API error: {e.status_code} - {e.detail}")
            status = 502 if e.status_code >= 500 else e.status_code
            return JSONResponse(
                status_code=status,
                content={
                    "status": "error",
                    "response": _user_friendly_php_error(e),
                    "detail": e.detail,
                },
            )

        except Exception as e:
            logger.exception(f"Unhandled error: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "response": "Ocorreu um erro interno. Por favor tenta novamente.",
                },
            )


def _user_friendly_php_error(e: PHPApiError) -> str:
    """Convert PHP API errors to user-friendly messages."""
    if e.status_code == 404:
        return "Recurso não encontrado."
    elif e.status_code == 400:
        if "nif" in e.detail.lower():
            return "Já existe um registo com este NIF."
        return f"Dados inválidos: {e.detail}"
    elif e.status_code == 503:
        return "O sistema principal está temporariamente indisponível. Tenta mais tarde."
    elif e.status_code == 504:
        return "Tempo de espera excedido ao contactar o sistema. Tenta novamente."
    else:
        return "Erro ao comunicar com o sistema."
