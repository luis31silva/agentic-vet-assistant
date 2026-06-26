from typing import Any, Dict, List

from loguru import logger

from app.tools.base import BaseTool
from app.utils.php_api_client import PHPApiClient, PHPApiError


class SearchPatientTool(BaseTool):
    name = "SEARCH_PATIENT"
    description = "Pesquisa pacientes (animais) por nome e/ou espécie."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """At least one search criterion must be provided."""
        name = payload.get("name")
        species = payload.get("species")
        if not name and not species:
            return {"valid": False, "errors": ["Preciso de pelo menos um critério de pesquisa (nome ou espécie)."]}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Search patients via PHP API."""
        try:
            name = payload.get("name")
            species = payload.get("species")
            results = await php_client.search_patients(name=name, species=species)

            if not results:
                return {
                    "success": True,
                    "message": "Não encontrei nenhum paciente com esses critérios.",
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
            logger.error(f"Search patient error: {e}")
            return {"success": False, "message": "Erro ao pesquisar pacientes.", "error": e.detail}
