from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.utils.php_api_client import PHPApiClient, PHPApiError


class GetAppointmentsTool(BaseTool):
    name = "GET_APPOINTMENTS"
    description = "Obtém as consultas de um paciente."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Requires patient_id."""
        patient_id = payload.get("patient_id")
        if not patient_id:
            return {"valid": False, "errors": ["Preciso do ID do paciente."]}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Fetch patient appointments."""
        try:
            patient_id = payload["patient_id"]
            appointments = await php_client.get_appointments_by_patient(patient_id)

            if not appointments:
                return {
                    "success": True,
                    "message": "Este paciente não tem consultas registadas.",
                    "data": [],
                    "count": 0,
                }

            return {
                "success": True,
                "message": f"{len(appointments)} consulta(s) encontrada(s).",
                "data": appointments,
                "count": len(appointments),
            }
        except PHPApiError as e:
            if e.status_code == 404:
                return {"success": False, "message": "Paciente não encontrado.", "error": e.detail}
            logger.error(f"Get appointments error: {e}")
            return {"success": False, "message": "Erro ao obter consultas.", "error": e.detail}
