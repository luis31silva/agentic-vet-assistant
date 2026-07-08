from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from loguru import logger

from app.schemas.models import ConversationState, OrchestratorResponse
from app.services.intent_service import IntentService
from app.agents.orchestrator import Orchestrator

router = APIRouter()
intent_service = IntentService()


class ChatRequest(BaseModel):
    conversation: ConversationState
    message: str
    images: List[str] = []


@router.post("/")
async def chat(req: ChatRequest, request: Request):
    """Main chat endpoint.

    Classifies user intent, extracts entities, and returns structured data.
    The frontend uses the intent + entities to decide what UI to show
    (open modal, navigate to page, or just display the chat response).

    No confirmation flow — the AI only classifies and extracts.
    Actual data creation happens through the existing frontend forms.

    Returns:
        {
            status: "ok",
            response: "text for the user",
            intent: "CREATE_OWNER_AND_PATIENT",
            confidence: 0.92,
            entities: { owner: {...}, patient: {...} },
            data: null | [...] (for search/get intents)
        }
    """
    try:
        logger.info(f"/chat received: conv_id={req.conversation.conversation_id}, msg_len={len(req.message)}, images={len(req.images)}")

        # Extract auth token for PHP API calls (search/get intents)
        auth_token = _extract_auth_token(request)

        # Classify intent + extract entities
        intent_result = await intent_service.classify(
            message=req.message,
            images=req.images,
            conversation=req.conversation,
        )

        logger.info(f"Intent: {intent_result.intent} (confidence={intent_result.confidence})")

        # For search/get intents, execute the query and return data
        if intent_result.intent in ("SEARCH_PATIENT", "SEARCH_OWNER", "GET_PATIENT_HISTORY", "GET_APPOINTMENTS", "GET_OWNER_PATIENTS"):
            orchestrator = Orchestrator(auth_token=auth_token)
            result = await orchestrator.handle(
                intent_result=intent_result,
                conversation=req.conversation,
                images=req.images,
            )
            return {
                "status": "ok",
                "response": result.response,
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                "entities": intent_result.entities,
                "data": result.data,
            }

        # For all other intents (CHAT, CREATE_*, ADD_VACCINES, etc.)
        # Just return the classification + entities — frontend handles the UI
        return {
            "status": "ok",
            "response": intent_result.response or "",
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": intent_result.entities,
            "data": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail="Erro interno ao processar a mensagem.")


def _extract_auth_token(request: Request) -> Optional[str]:
    """Extract Bearer token from request headers."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return None
