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
    "CHAT",
]


class IntentService:
    def __init__(self):
        self.model = get_model_provider()

    async def classify(self, message: str, images: List[str], conversation) -> IntentResult:
        # Build a short prompt asking the model to pick one of VALID_INTENTS and extract entities
        system = (
            "You are a professional veterinary assistant. "
            "Your task is to classify user input into one of these intents: " + ",".join(VALID_INTENTS) + ". "
            "Use 'CHAT' if the user is greeting, asking clinical questions, seeking veterinary advice, or talking about anything related to veterinary care."
            "If you receive images, analyze them and include any relevant information in your classification. If the intent is per example 'ADD_VACCINES', extract the vaccine names and dates from the images if possible."
            "Respond in JSON with these keys: "
            "1. 'intent': The classification. "
            "2. 'confidence': A float between 0 and 1. "
            "3. 'entities': A dictionary of extracted entities. "
            "4. 'response': A human-readable text response (mandatory if intent is CHAT, optional otherwise). "
            "Always respond in Portuguese (Portugal)."
        )
        user_content = f"Message: {message}\nConversation history: {conversation.history if conversation else '[]'}"
        messages = [
            {"role": "system", "content": system}, 
            {"role": "user", "content": user_content, "images": images}
        ]
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
                return IntentResult(intent=intent.upper(), confidence=float(j.get("confidence", 1.0)), entities=j.get("entities", {}), response=j.get("response", ""))
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
