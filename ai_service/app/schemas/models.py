from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PendingAction(BaseModel):
    action_id: Optional[str]
    tool: Optional[str]
    payload: Optional[Dict[str, Any]]
    workflow_state: Optional[WorkflowState]


class ConversationState(BaseModel):
    conversation_id: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    pending_action: Optional[PendingAction]


class IntentResult(BaseModel):
    intent: str
    confidence: float = 0.0
    entities: Dict[str, Any] = Field(default_factory=dict)


class CreateOwnerRequest(BaseModel):
    name: str
    phone: Optional[str]
    email: Optional[str]


class CreatePatientRequest(BaseModel):
    name: str
    species: Optional[str]
    breed: Optional[str]
    birth_date: Optional[str]
    owner_id: Optional[int]


class AddVaccinesRequest(BaseModel):
    patient_id: int
    vaccines: List[Dict[str, Any]]
