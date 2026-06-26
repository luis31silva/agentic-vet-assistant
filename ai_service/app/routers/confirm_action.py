from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from loguru import logger

from app.schemas.models import ConversationState, OrchestratorResponse, PendingAction, WorkflowState
from app.agents.workflow_engine import WorkflowEngine

router = APIRouter()


class ConfirmRequest(BaseModel):
    conversation: ConversationState
    message: str


@router.post("/")
async def confirm(req: ConfirmRequest, request: Request):
    """Confirm or cancel a pending action.

    This is an alternative to using /chat for confirmations.
    The PHP backend can call this directly when it knows
    the user is responding to a pending action.

    Body:
        conversation: ConversationState with pending_action set
        message: user's reply ("sim", "não", or corrections)

    Returns:
        OrchestratorResponse with execution result or cancellation
    """
    try:
        if not req.conversation.pending_action:
            raise HTTPException(status_code=400, detail="Não existe ação pendente para confirmar.")

        # Extract auth token
        auth_token = _extract_auth_token(request)

        engine = WorkflowEngine(auth_token=auth_token)
        decision = await engine.handle_user_reply(req.conversation, req.message)

        action = decision.get("action", "none")

        # Map engine decisions to OrchestratorResponse
        if action == "executed":
            result_data = decision.get("result", {})
            return OrchestratorResponse(
                response=result_data.get("message", "Ação executada com sucesso!"),
                intent=req.conversation.pending_action.tool,
                pending_action=PendingAction(workflow_state=WorkflowState.COMPLETED),
                data=result_data.get("data"),
            ).model_dump()

        elif action == "executed_with_corrections":
            result_data = decision.get("result", {})
            return OrchestratorResponse(
                response=result_data.get("message", "Ação executada com correções!"),
                intent=req.conversation.pending_action.tool,
                pending_action=PendingAction(workflow_state=WorkflowState.COMPLETED),
                data=result_data.get("data"),
            ).model_dump()

        elif action == "cancelled":
            return OrchestratorResponse(
                response="Ação cancelada. Em que mais posso ajudar?",
                intent=req.conversation.pending_action.tool,
                pending_action=PendingAction(workflow_state=WorkflowState.CANCELLED),
            ).model_dump()

        elif action == "validation_failed":
            errors = decision.get("errors", [])
            error_msg = ", ".join(errors) if errors else "Dados inválidos"
            return OrchestratorResponse(
                response=f"Não foi possível executar: {error_msg}. Podes corrigir os dados?",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

        elif action == "still_missing":
            errors = decision.get("errors", [])
            error_msg = ", ".join(errors) if errors else "Campos em falta"
            return OrchestratorResponse(
                response=f"Ainda faltam dados: {error_msg}",
                intent=req.conversation.pending_action.tool,
                pending_action=PendingAction(
                    action_id=req.conversation.pending_action.action_id,
                    tool=req.conversation.pending_action.tool,
                    payload=decision.get("payload", req.conversation.pending_action.payload),
                    workflow_state=WorkflowState.MISSING_REQUIRED_FIELDS,
                    missing_fields=errors,
                ),
            ).model_dump()

        elif action == "execution_error":
            return OrchestratorResponse(
                response=f"Erro ao executar a ação: {decision.get('error', 'erro desconhecido')}. Tenta novamente.",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

        elif action == "invalid_tool":
            return OrchestratorResponse(
                response=f"Ferramenta '{decision.get('tool')}' não reconhecida.",
                intent=req.conversation.pending_action.tool,
                pending_action=PendingAction(workflow_state=WorkflowState.CANCELLED),
            ).model_dump()

        elif action == "unable_to_parse_corrections":
            return OrchestratorResponse(
                response="Não consegui perceber a correção. Podes reformular ou dizer 'sim' para confirmar ou 'não' para cancelar?",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

        else:
            return OrchestratorResponse(
                response="Não percebi a tua resposta. Diz 'sim' para confirmar ou 'não' para cancelar.",
                intent=req.conversation.pending_action.tool,
                pending_action=req.conversation.pending_action,
            ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("confirm action error")
        raise HTTPException(status_code=500, detail="Erro ao processar a confirmação.")


def _extract_auth_token(request: Request) -> Optional[str]:
    """Extract Bearer token from request headers."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return None
