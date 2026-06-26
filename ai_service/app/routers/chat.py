from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from loguru import logger

from app.schemas.models import ConversationState, OrchestratorResponse, WorkflowState
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

    Handles the full conversational flow:
    1. If pending_action with WAITING_CONFIRMATION → handle confirmation
    2. If pending_action with MISSING_REQUIRED_FIELDS → try to extract missing data
    3. Otherwise → classify intent → orchestrate

    Body:
        conversation: { conversation_id, history, pending_action }
        message: current user message
        images: list of base64 images (optional)

    Returns:
        OrchestratorResponse: { status, response, intent, pending_action, data }
    """
    try:
        logger.info(f"/chat received: conv_id={req.conversation.conversation_id}, msg_len={len(req.message)}, images={len(req.images)}")

        # Extract auth token for PHP API calls
        auth_token = _extract_auth_token(request)

        # Create orchestrator instance with auth
        orchestrator = Orchestrator(auth_token=auth_token)

        # --- Flow routing based on conversation state ---

        pending = req.conversation.pending_action

        # Case 1: User is confirming or cancelling a pending action
        if pending and pending.workflow_state == WorkflowState.WAITING_CONFIRMATION:
            return await _handle_confirmation(req, orchestrator)

        # Case 2: User is providing missing data for a pending action
        if pending and pending.workflow_state == WorkflowState.MISSING_REQUIRED_FIELDS:
            return await _handle_missing_data(req, orchestrator)

        # Case 3: Fresh message — classify intent and orchestrate
        return await _handle_new_message(req, orchestrator)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail="Erro interno ao processar a mensagem.")


async def _handle_new_message(req: ChatRequest, orchestrator: Orchestrator) -> dict:
    """Classify intent and route through orchestrator."""
    # Classify intent
    intent_result = await intent_service.classify(
        message=req.message,
        images=req.images,
        conversation=req.conversation,
    )

    logger.info(f"Intent classified: {intent_result.intent} (confidence={intent_result.confidence})")

    # Route through orchestrator
    result = await orchestrator.handle(
        intent_result=intent_result,
        conversation=req.conversation,
        images=req.images,
    )

    return result.model_dump()


async def _handle_confirmation(req: ChatRequest, orchestrator: Orchestrator) -> dict:
    """Handle user confirmation/cancellation of a pending action."""
    from app.agents.workflow_engine import WorkflowEngine

    message_lower = req.message.strip().lower()

    # Check for explicit confirmation
    if message_lower in ("sim", "yes", "confirmo", "confirma", "s"):
        engine = WorkflowEngine(auth_token=_extract_auth_token_from_orchestrator(orchestrator))
        decision = await engine.handle_user_reply(req.conversation, req.message)

        if decision.get("action") == "executed":
            result_data = decision.get("result", {})
            message = result_data.get("message", "Ação executada com sucesso!")
            return OrchestratorResponse(
                response=message,
                intent=req.conversation.pending_action.tool,
                pending_action=None,
                data=result_data,
            ).model_dump()

        elif decision.get("action") == "executed_with_corrections":
            result_data = decision.get("result", {})
            message = result_data.get("message", "Ação executada com correções!")
            return OrchestratorResponse(
                response=message,
                intent=req.conversation.pending_action.tool,
                pending_action=None,
                data=result_data,
            ).model_dump()

        elif decision.get("action") == "validation_failed":
            errors = decision.get("errors", [])
            return OrchestratorResponse(
                response=f"Não foi possível executar: {', '.join(errors)}",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

        else:
            return OrchestratorResponse(
                response="Ocorreu um problema ao executar. Tenta novamente.",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

    # Check for explicit cancellation
    elif message_lower in ("não", "nao", "no", "cancela", "cancelar", "n"):
        return orchestrator._handle_cancel().model_dump()

    # Ambiguous reply — re-classify as it might be a correction or new intent
    else:
        # Maybe user is providing corrections or changing their mind
        intent_result = await intent_service.classify(
            message=req.message,
            images=req.images,
            conversation=req.conversation,
        )

        # If it's a CANCEL, cancel
        if intent_result.intent == "CANCEL_ACTION":
            return orchestrator._handle_cancel().model_dump()

        # Otherwise, treat as correction — try to re-handle with merged data
        result = await orchestrator.handle(
            intent_result=intent_result,
            conversation=req.conversation,
            images=req.images,
        )
        return result.model_dump()


async def _handle_missing_data(req: ChatRequest, orchestrator: Orchestrator) -> dict:
    """Handle user providing missing required fields."""
    # Classify the reply to extract entities
    intent_result = await intent_service.classify(
        message=req.message,
        images=req.images,
        conversation=req.conversation,
    )

    # If user wants to cancel
    if intent_result.intent == "CANCEL_ACTION":
        return orchestrator._handle_cancel().model_dump()

    # Let orchestrator handle the merge (it checks for pending_action MISSING state)
    result = await orchestrator.handle(
        intent_result=intent_result,
        conversation=req.conversation,
        images=req.images,
    )

    return result.model_dump()


def _extract_auth_token(request: Request) -> Optional[str]:
    """Extract Bearer token from request headers."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def _extract_auth_token_from_orchestrator(orchestrator: Orchestrator) -> Optional[str]:
    """Extract auth token from orchestrator's PHP client."""
    return orchestrator.php.auth_token
