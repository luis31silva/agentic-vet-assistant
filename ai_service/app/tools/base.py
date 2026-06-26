from typing import Any, Dict

from app.utils.php_api_client import PHPApiClient


class BaseTool:
    """Base class for all tools.

    Each tool knows how to:
    - validate a payload (check required fields, types)
    - execute the action (call PHP API)
    """

    name: str = ""
    description: str = ""

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the payload before execution.

        Returns:
            {"valid": True} or {"valid": False, "errors": ["..."]}
        """
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Execute the tool action via the PHP API.

        Returns:
            Result dict from the API, or error information.
        """
        raise NotImplementedError(f"Tool {self.name} has not implemented execute()")
