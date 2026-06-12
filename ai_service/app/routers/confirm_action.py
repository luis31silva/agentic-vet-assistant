from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.models import ConversationState
from app.agents.workflow_engine import WorkflowEngine
from loguru import logger

router = APIRouter()
engine = WorkflowEngine()


class ConfirmRequest(BaseModel):
    conversation: ConversationState
    message: str


@router.post("/")
async def confirm(req: ConfirmRequest):
    try:
        decision = await engine.handle_user_reply(req.conversation, req.message)
        return {"status": "ok", "decision": decision}
    except Exception as e:
        logger.exception("confirm error")
        raise HTTPException(status_code=500, detail=str(e))
