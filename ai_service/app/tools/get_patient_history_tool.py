from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.utils.php_api_client import PHPApiClient, PHPApiError


class GetPatientHistoryTool(BaseTool):
    name = "GET_PATIENT_HISTORY"
    description = "Obtém o histórico clínico completo de um paciente."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Requires patient_id."""
        patient_id = payload.get("patient_id")
        if not patient_id:
            return {"valid": False, "errors": ["Preciso do ID do paciente."]}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Fetch patient clinical history."""
        try:
            patient_id = payload["patient_id"]
            history = await php_client.get_patient_history(patient_id)

            if not history:
                return {
                    "success": True,
                    "message": "Este paciente não tem histórico clínico registado.",
                    "data": [],
                    "count": 0,
                }

            return {
                "success": True,
                "message": f"Histórico com {len(history)} entrada(s).",
                "data": history,
                "count": len(history),
            }
        except PHPApiError as e:
            if e.status_code == 404:
                return {"success": False, "message": "Paciente não encontrado.", "error": e.detail}
            logger.error(f"Get patient history error: {e}")
            return {"success": False, "message": "Erro ao obter histórico.", "error": e.detail}
