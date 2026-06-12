from typing import Any, Dict
from pydantic import BaseModel


class ToolSchema(BaseModel):
    name: str
    description: str


class BaseTool:
    name: str

    def schema(self) -> ToolSchema:
        raise NotImplementedError()

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Return dict with keys: valid(bool), errors(list)
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client) -> Dict[str, Any]:
        raise NotImplementedError()
