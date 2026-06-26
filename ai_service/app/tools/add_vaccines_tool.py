from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.schemas.models import AddVaccinesRequest
from app.utils.php_api_client import PHPApiClient, PHPApiError


class AddVaccinesTool(BaseTool):
    name = "ADD_VACCINES"
    description = "Regista vacinas para um paciente existente."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate vaccines payload."""
        try:
            AddVaccinesRequest(**payload)
            return {"valid": True, "errors": []}
        except Exception as e:
            errors = []
            if hasattr(e, "errors"):
                for err in e.errors():
                    field = ".".join(str(loc) for loc in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    errors.append(f"{field}: {msg}")
            else:
                errors.append(str(e))
            return {"valid": False, "errors": errors}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Add vaccines via appointment creation in PHP API."""
        try:
            # Build appointment payload with vaccines
            appointment_payload = {
                "patient_id": payload["patient_id"],
                "appointment_type_id": payload.get("appointment_type_id", 1),
                "vaccines": payload.get("vaccines", []),
            }
            result = await php_client.create_appointment(appointment_payload)
            logger.info(f"Vaccines added for patient {payload['patient_id']}")
            return {
                "success": True,
                "message": f"Vacinas registadas com sucesso para o paciente (ID: {payload['patient_id']})!",
                "data": result,
            }
        except PHPApiError as e:
            logger.error(f"Failed to add vaccines: {e}")
            return {
                "success": False,
                "message": f"Erro ao registar vacinas: {e.detail}",
                "error": e.detail,
            }
