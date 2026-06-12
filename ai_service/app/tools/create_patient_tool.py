from typing import Any, Dict
from app.tools.base import BaseTool
from app.schemas.models import CreatePatientRequest


class CreatePatientTool(BaseTool):
    name = "CREATE_PATIENT"

    def schema(self):
        return CreatePatientRequest.schema()

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            CreatePatientRequest(**payload)
            return {"valid": True, "errors": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}

    async def execute(self, payload: Dict[str, Any], php_client) -> Dict[str, Any]:
        # Call PHP API to create patient
        return await php_client.create_patient(payload)
