from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.utils.php_api_client import PHPApiClient, PHPApiError


class SearchOwnerTool(BaseTool):
    name = "SEARCH_OWNER"
    description = "Pesquisa tutores (donos) por nome e/ou NIF."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """At least one search criterion must be provided."""
        name = payload.get("name")
        nif = payload.get("nif")
        if not name and not nif:
            return {"valid": False, "errors": ["Preciso de pelo menos um critério de pesquisa (nome ou NIF)."]}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Search owners via PHP API."""
        try:
            name = payload.get("name")
            nif = payload.get("nif")
            results = await php_client.search_owners(name=name, nif=nif)

            if not results:
                return {
                    "success": True,
                    "message": "Não encontrei nenhum tutor com esses critérios.",
                    "data": [],
                    "count": 0,
                }

            return {
                "success": True,
                "message": f"Encontrei {len(results)} resultado(s).",
                "data": results,
                "count": len(results),
            }
        except PHPApiError as e:
            logger.error(f"Search owner error: {e}")
            return {"success": False, "message": "Erro ao pesquisar tutores.", "error": e.detail}
