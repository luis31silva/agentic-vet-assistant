from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.schemas.models import CreateOwnerRequest
from app.utils.php_api_client import PHPApiClient, PHPApiError


class CreateOwnerTool(BaseTool):
    name = "CREATE_OWNER"
    description = "Cria um novo tutor (dono) no sistema."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate owner payload against CreateOwnerRequest schema."""
        try:
            CreateOwnerRequest(**payload)
            return {"valid": True, "errors": []}
        except Exception as e:
            errors = []
            # Extract field-level errors from Pydantic
            if hasattr(e, "errors"):
                for err in e.errors():
                    field = ".".join(str(loc) for loc in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    errors.append(f"{field}: {msg}")
            else:
                errors.append(str(e))
            return {"valid": False, "errors": errors}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Create owner via PHP API."""
        try:
            result = await php_client.create_owner(payload)
            owner_id = result.get("id")
            logger.info(f"Owner created successfully: ID={owner_id}, name={payload.get('name')}")
            return {
                "success": True,
                "message": f"Tutor '{payload.get('name')}' criado com sucesso!",
                "owner_id": owner_id,
                "data": result,
            }
        except PHPApiError as e:
            logger.error(f"Failed to create owner: {e}")
            # User-friendly error messages
            if e.status_code == 400:
                if "nif" in e.detail.lower() or "duplicat" in e.detail.lower():
                    return {"success": False, "message": "Já existe um tutor com este NIF.", "error": e.detail}
                return {"success": False, "message": f"Dados inválidos: {e.detail}", "error": e.detail}
            return {"success": False, "message": "Erro ao criar o tutor. Tenta novamente.", "error": e.detail}
