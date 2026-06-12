from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.models import ConversationState, IntentResult
from app.services.intent_service import IntentService
from loguru import logger

router = APIRouter()
intent_service = IntentService()


class ChatRequest(BaseModel):
    conversation: ConversationState
    message: str
    images: list = []


@router.post("/")
async def chat(req: ChatRequest):
    try:
        logger.info("/chat received message")
        intent_result: IntentResult = await intent_service.classify(req.message, req.images, req.conversation)
        return {"status": "ok", "intent": intent_result.dict()}
    except Exception as e:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail=str(e))
