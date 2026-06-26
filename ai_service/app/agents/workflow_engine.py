import json
from typing import Any, Dict, Optional

from loguru import logger

from app.schemas.models import ConversationState, PendingAction, WorkflowState
from app.providers.factory import get_model_provider
from app.tools.registry import tool_registry
from app.utils.php_api_client import PHPApiClient


class WorkflowEngine:
    """Handles execution of confirmed actions.

    When a user confirms a pending action, this engine validates
    the payload and executes the tool via the PHP API.
    """

    def __init__(self, auth_token: Optional[str] = None):
        self.model_provider = get_model_provider()
        self.php = PHPApiClient(auth_token=auth_token)

    async def handle_user_reply(self, conversation: ConversationState, message: str) -> Dict[str, Any]:
        """Process user reply to a pending action.

        Handles:
        - Explicit confirmation ("sim") → validate + execute
        - Explicit cancellation ("não") → cancel
        - Other text → attempt LLM-based correction
        """
        pa = conversation.pending_action
        if not pa:
            return {"action": "none"}

        tool_name = (pa.tool or "").upper()
        tool = tool_registry.get(tool_name)
        if not tool:
            logger.warning(f"Unknown tool in pending action: {tool_name}")
            return {"action": "invalid_tool", "tool": tool_name}

        # Explicit confirmation
        if message.strip().lower() in ("sim", "yes", "confirmo", "confirma", "s"):
            return await self._execute_action(tool, pa)

        # Explicit cancellation
        if message.strip().lower() in ("não", "nao", "no", "cancela", "n"):
            return {"action": "cancelled"}

        # Ambiguous reply — try LLM-based correction
        return await self._attempt_correction(tool, pa, message)

    async def _execute_action(self, tool, pa: PendingAction) -> Dict[str, Any]:
        """Validate and execute a confirmed action."""
        payload = pa.payload or {}

        valid = await tool.validate(payload)
        if not valid.get("valid"):
            return {"action": "validation_failed", "errors": valid.get("errors", [])}

        try:
            result = await tool.execute(payload, self.php)
            return {"action": "executed", "result": result}
        except Exception as e:
            logger.exception(f"Error executing tool {tool.name}")
            return {"action": "execution_error", "error": str(e)}

    async def _attempt_correction(self, tool, pa: PendingAction, message: str) -> Dict[str, Any]:
        """Use LLM to extract corrections from user message and re-execute."""
        messages = [
            {
                "role": "system",
                "content": (
                    "O utilizador está a corrigir dados de um formulário. "
                    "Analisa a mensagem e retorna APENAS um JSON com os campos corrigidos. "
                    "Não incluas campos que não foram mencionados."
                ),
            },
            {
                "role": "user",
                "content": f"Payload atual: {json.dumps(pa.payload, ensure_ascii=False)}\nMensagem do utilizador: {message}\nRetorna JSON com correções:",
            },
        ]

        try:
            resp = await self.model_provider.chat(messages)
            choices = resp.get("choices", [])
            if not choices:
                return {"action": "unable_to_parse_corrections", "raw": ""}

            text = choices[0].get("message", {}).get("content", "")

            # Clean JSON from markdown blocks
            json_str = text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            corrected = json.loads(json_str)

            # Merge corrections into payload
            payload = dict(pa.payload or {})

            # Handle nested payloads (owner + patient)
            if "owner" in payload and "owner" in corrected:
                payload["owner"].update(corrected["owner"])
                corrected.pop("owner")
            if "patient" in payload and "patient" in corrected:
                payload["patient"].update(corrected["patient"])
                corrected.pop("patient")

            # Merge remaining flat fields
            payload.update(corrected)

            # Validate corrected payload
            valid = await tool.validate(payload)
            if valid.get("valid"):
                result = await tool.execute(payload, self.php)
                return {"action": "executed_with_corrections", "result": result}
            else:
                return {"action": "still_missing", "errors": valid.get("errors", []), "payload": payload}

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse correction JSON from LLM")
            return {"action": "unable_to_parse_corrections", "raw": text if 'text' in dir() else ""}
        except Exception:
            logger.exception("Error in correction attempt")
            return {"action": "unable_to_parse_corrections", "raw": ""}
