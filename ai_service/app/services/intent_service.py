from typing import Any, Dict, List
from app.providers.factory import get_model_provider
from app.schemas.models import IntentResult
from loguru import logger


VALID_INTENTS = [
    "CREATE_PATIENT",
    "CREATE_OWNER",
    "ADD_VACCINES",
    "UPDATE_PATIENT",
    "CANCEL_ACTION",
]


class IntentService:
    def __init__(self):
        self.model = get_model_provider()

    async def classify(self, message: str, images: List[str], conversation) -> IntentResult:
        # Build a short prompt asking the model to pick one of VALID_INTENTS and extract entities
        system = (
            "You are an assistant that maps user messages to one of the allowed intents and extracts entities. "
            "Allowed intents: " + ",".join(VALID_INTENTS) + ". Respond in JSON with keys: intent, confidence, entities. "
            "Do not invent endpoints or perform CRUD."
        )
        user = f"Message: {message}\nImages: {images}\nConversation history: {conversation.history if conversation else '[]'}"
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        resp = await self.model.chat(messages)
        choices = resp.get("choices", [])
        if not choices:
            return IntentResult(intent="UNKNOWN", confidence=0.0, entities={})
        content = choices[0].get("message", {}).get("content", "")
        # Try parse JSON out of content
        import json
        try:
            j = json.loads(content)
            intent = j.get("intent") or j.get("action")
            if intent and intent.upper() in VALID_INTENTS:
                return IntentResult(intent=intent.upper(), confidence=float(j.get("confidence", 1.0)), entities=j.get("entities", {}))
            else:
                # fallback simple rules
                text = message.lower()
                if "vacina" in text or "vacinas" in text or "vacina" in (" ".join(images)).lower():
                    return IntentResult(intent="ADD_VACCINES", confidence=0.85, entities={})
                if "paciente" in text or "animal" in text:
                    return IntentResult(intent="CREATE_PATIENT", confidence=0.8, entities={})
        except Exception:
            logger.exception("failed to parse intent response")
        return IntentResult(intent="UNKNOWN", confidence=0.0, entities={})
