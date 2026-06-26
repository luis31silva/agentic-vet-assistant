from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.utils.php_api_client import PHPApiClient, PHPApiError


class GetOwnerPatientsTool(BaseTool):
    name = "GET_OWNER_PATIENTS"
    description = "Lista todos os animais de um tutor."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Requires owner_id."""
        owner_id = payload.get("owner_id")
        if not owner_id:
            return {"valid": False, "errors": ["Preciso do ID do tutor."]}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Fetch all patients for an owner."""
        try:
            owner_id = payload["owner_id"]
            patients = await php_client.get_patients_by_owner(owner_id)

            if not patients:
                return {
                    "success": True,
                    "message": "Este tutor não tem animais registados.",
                    "data": [],
                    "count": 0,
                }

            return {
                "success": True,
                "message": f"{len(patients)} animal(is) encontrado(s).",
                "data": patients,
                "count": len(patients),
            }
        except PHPApiError as e:
            if e.status_code == 404:
                return {"success": False, "message": "Tutor não encontrado.", "error": e.detail}
            logger.error(f"Get owner patients error: {e}")
            return {"success": False, "message": "Erro ao obter animais do tutor.", "error": e.detail}
