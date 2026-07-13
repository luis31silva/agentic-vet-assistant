from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ===========================
# CONVERSATION STATE
# ===========================


class ConversationState(BaseModel):
    conversation_id: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    entities: Optional[Dict[str, Any]] = None  # last_entities from previous turn


# ===========================
# INTENT
# ===========================


class IntentResult(BaseModel):
    intent: str
    confidence: float = 0.0
    entities: Dict[str, Any] = Field(default_factory=dict)
    response: Optional[str] = None


# ===========================
# CLINICAL ADVICE
# ===========================


class ClinicalAdviceRequest(BaseModel):
    patient_id: int
    symptoms: str
    appointment_context: Optional[str] = None


# ===========================
# ORCHESTRATOR RESPONSE (for search/get intents only)
# ===========================


class OrchestratorResponse(BaseModel):
    """Response from orchestrator for query intents."""
    status: str = "ok"
    response: str = Field(description="Human-readable text response for the user")
    intent: Optional[str] = None
    data: Optional[Any] = None
