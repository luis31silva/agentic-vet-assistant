from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ===========================
# CONVERSATION STATE (simplified - no pending_action)
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
# OWNER SCHEMAS (matches PHP API: OwnerCreate)
# Required: name, nif
# ===========================


class CreateOwnerRequest(BaseModel):
    name: str
    nif: str
    phone_number: Optional[str] = None
    phone_number2: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def required_fields(cls) -> List[str]:
        return ["name", "nif"]


# ===========================
# PATIENT SCHEMAS (matches PHP API: PatientCreate)
# Required: name, owner (int - owner_id)
# ===========================


class CreatePatientRequest(BaseModel):
    name: str
    owner: int = Field(description="Owner ID")
    species: Optional[str] = None
    breed: Optional[str] = None
    weight: Optional[float] = None
    birth_date: Optional[str] = None
    microchip: Optional[str] = None

    @classmethod
    def required_fields(cls) -> List[str]:
        return ["name", "owner"]


# ===========================
# PATIENT WITHOUT OWNER (for composite creation)
# ===========================


class PatientData(BaseModel):
    """Patient data without owner field (owner injected after creation)."""
    name: str
    species: Optional[str] = None
    breed: Optional[str] = None
    weight: Optional[float] = None
    birth_date: Optional[str] = None
    microchip: Optional[str] = None

    @classmethod
    def required_fields(cls) -> List[str]:
        return ["name"]


# ===========================
# COMPOSITE: OWNER + PATIENT
# ===========================


class CreateOwnerAndPatientRequest(BaseModel):
    owner: CreateOwnerRequest
    patient: PatientData

    @classmethod
    def required_fields(cls) -> List[str]:
        return ["owner.name", "owner.nif", "patient.name"]


# ===========================
# VACCINES
# ===========================


class AddVaccinesRequest(BaseModel):
    patient_id: int
    appointment_type_id: int = 1
    vaccines: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def required_fields(cls) -> List[str]:
        return ["patient_id", "vaccines"]


# ===========================
# CLINICAL ADVICE
# ===========================


class ClinicalAdviceRequest(BaseModel):
    patient_id: int
    symptoms: str
    appointment_context: Optional[str] = None


# ===========================
# SEARCH / QUERY
# ===========================


class SearchQuery(BaseModel):
    query: Optional[str] = None
    name: Optional[str] = None
    nif: Optional[str] = None
    species: Optional[str] = None
    patient_id: Optional[int] = None
    owner_id: Optional[int] = None


# ===========================
# ORCHESTRATOR RESPONSE (for search/get intents only)
# ===========================


class OrchestratorResponse(BaseModel):
    """Response from orchestrator for query intents."""
    status: str = "ok"
    response: str = Field(description="Human-readable text response for the user")
    intent: Optional[str] = None
    data: Optional[Any] = None
