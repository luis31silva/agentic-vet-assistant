from typing import Any, Dict
from app.tools.base import BaseTool
from app.schemas.models import AddVaccinesRequest


class AddVaccinesTool(BaseTool):
    name = "ADD_VACCINES"

    def schema(self):
        return AddVaccinesRequest.schema()

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            AddVaccinesRequest(**payload)
            return {"valid": True, "errors": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}

    async def execute(self, payload: Dict[str, Any], php_client) -> Dict[str, Any]:
        return await php_client.add_vaccines(payload)
