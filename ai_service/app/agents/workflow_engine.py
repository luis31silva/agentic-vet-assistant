from typing import Any, Dict
from app.schemas.models import ConversationState, PendingAction, WorkflowState
from app.providers.factory import get_model_provider
from loguru import logger
from app.tools.create_patient_tool import CreatePatientTool
from app.tools.add_vaccines_tool import AddVaccinesTool
from app.utils.php_api_client import PHPApiClient


class WorkflowEngine:
    def __init__(self):
        self.model_provider = get_model_provider()
        self.tools = {"CREATE_PATIENT": CreatePatientTool(), "ADD_VACCINES": AddVaccinesTool()}
        self.php = PHPApiClient()

    async def handle_user_reply(self, conversation: ConversationState, message: str) -> Dict[str, Any]:
        # Very small orchestration: if pending_action exists, validate user reply
        pa = conversation.pending_action
        if not pa:
            return {"action": "none"}

        tool_name = (pa.tool or "").upper()
        tool = self.tools.get(tool_name)
        if not tool:
            return {"action": "invalid_tool", "tool": tool_name}

        # If message is an explicit confirmation
        if message.strip().lower() in ["sim", "yes"]:
            # validate and execute
            valid = await tool.validate(pa.payload or {})
            if valid.get("valid"):
                result = await tool.execute(pa.payload or {}, self.php)
                return {"action": "executed", "result": result}
            else:
                return {"action": "validation_failed", "errors": valid.get("errors")}

        if message.strip().lower() in ["não", "nao", "no"]:
            return {"action": "cancelled"}

        # Otherwise we ask LLM for suggested corrections (simple)
        messages = [
            {"role": "system", "content": "You help produce JSON payload corrections for fields."},
            {"role": "user", "content": f"Pending payload: {pa.payload} - User says: {message}. Return a JSON with corrected fields only."},
        ]
        resp = await self.model_provider.chat(messages)
        # naive extraction
        choices = resp.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")
            # We expect the model to respond with JSON; attempt parse
            import json

            try:
                corrected = json.loads(text)
                # merge into payload
                payload = dict(pa.payload or {})
                payload.update(corrected)
                valid = await tool.validate(payload)
                if valid.get("valid"):
                    result = await tool.execute(payload, self.php)
                    return {"action": "executed_with_corrections", "result": result}
                else:
                    return {"action": "still_missing", "errors": valid.get("errors")}
            except Exception:
                logger.exception("failed to parse correction from LLM")
                return {"action": "unable_to_parse_corrections", "raw": text}
