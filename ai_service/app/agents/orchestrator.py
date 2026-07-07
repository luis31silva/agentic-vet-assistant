import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

from app.schemas.models import (
    ConversationState,
    CreateOwnerAndPatientRequest,
    CreateOwnerRequest,
    CreatePatientRequest,
    IntentResult,
    OrchestratorResponse,
    PatientData,
    PendingAction,
    WorkflowState,
)
from app.utils.php_api_client import PHPApiClient, PHPApiError
from app.utils.normalizer import normalize_entities


# Maps intent → required fields for that action
REQUIRED_FIELDS_MAP = {
    "CREATE_OWNER_AND_PATIENT": ["owner.name", "owner.nif", "patient.name"],
    "CREATE_OWNER": ["name", "nif"],
    "CREATE_PATIENT": ["name", "owner"],
    "ADD_VACCINES": ["patient_id", "vaccines"],
}

# Maps intent → tool name
INTENT_TO_TOOL = {
    "CREATE_OWNER_AND_PATIENT": "CREATE_OWNER_AND_PATIENT",
    "CREATE_OWNER": "CREATE_OWNER",
    "CREATE_PATIENT": "CREATE_PATIENT",
    "ADD_VACCINES": "ADD_VACCINES",
}


class Orchestrator:
    """Central orchestration component.

    Receives classified intent + entities + conversation state and decides
    the next step: respond directly, ask for missing data, ask for confirmation,
    or execute queries.
    """

    def __init__(self, auth_token: Optional[str] = None):
        self.php = PHPApiClient(auth_token=auth_token)

    async def handle(
        self,
        intent_result: IntentResult,
        conversation: ConversationState,
        images: List[str] = None,
    ) -> OrchestratorResponse:
        """Main entry point. Routes to the appropriate handler based on intent."""
        intent = intent_result.intent
        entities = intent_result.entities
        response_text = intent_result.response or ""

        logger.info(f"Orchestrator handling intent: {intent} (confidence: {intent_result.confidence})")

        # Check if we're in a pending action flow (user providing missing data)
        if conversation.pending_action and conversation.pending_action.workflow_state == WorkflowState.MISSING_REQUIRED_FIELDS:
            return await self._handle_missing_data_reply(intent_result, conversation)

        # Route by intent type
        if intent == "CHAT":
            return self._handle_chat(response_text)

        elif intent == "CANCEL_ACTION":
            return self._handle_cancel()

        elif intent in INTENT_TO_TOOL:
            return await self._handle_create(intent, entities, response_text)

        elif intent in ("SEARCH_PATIENT", "SEARCH_OWNER"):
            return await self._handle_search(intent, entities)

        elif intent in ("GET_PATIENT_HISTORY", "GET_APPOINTMENTS", "GET_OWNER_PATIENTS"):
            return await self._handle_get(intent, entities)

        elif intent == "CLINICAL_ADVICE":
            # This should come through /clinical-advice endpoint, but handle gracefully
            return OrchestratorResponse(
                response="Para obter conselhos clínicos, por favor usa o botão dedicado durante a consulta com o ID do paciente e os sintomas.",
                intent=intent,
            )

        else:
            return OrchestratorResponse(
                response=response_text or "Desculpa, não percebi o que pretendes. Podes reformular?",
                intent=intent,
            )

    # ===========================
    # CHAT
    # ===========================

    def _handle_chat(self, response_text: str) -> OrchestratorResponse:
        """Handle conversational messages."""
        return OrchestratorResponse(
            response=response_text or "Em que posso ajudar?",
            intent="CHAT",
        )

    # ===========================
    # CANCEL
    # ===========================

    def _handle_cancel(self) -> OrchestratorResponse:
        """Cancel the current pending action."""
        return OrchestratorResponse(
            response="Ação cancelada. Em que mais posso ajudar?",
            intent="CANCEL_ACTION",
            pending_action=PendingAction(workflow_state=WorkflowState.CANCELLED),
        )

    # ===========================
    # CREATE (owner, patient, composite, vaccines)
    # ===========================

    async def _handle_create(
        self, intent: str, entities: Dict[str, Any], response_text: str
    ) -> OrchestratorResponse:
        """Handle creation intents: validate fields, ask for missing, or confirm."""
        tool = INTENT_TO_TOOL[intent]
        required = REQUIRED_FIELDS_MAP[intent]

        # Build payload from entities
        payload = self._build_payload(intent, entities)

        # Check for missing required fields
        missing = self._find_missing_fields(intent, payload)

        if missing:
            # Ask user for missing fields
            missing_labels = self._format_missing_fields(missing)
            summary = self._format_payload_summary(intent, payload)

            response = ""
            if summary:
                response += f"{summary}\n\n"
            response += f"Para continuar, preciso que me indiques: {missing_labels}"

            if response_text and not summary:
                response = f"{response_text}\n\nFalta: {missing_labels}"

            return OrchestratorResponse(
                response=response,
                intent=intent,
                pending_action=PendingAction(
                    action_id=str(uuid.uuid4()),
                    tool=tool,
                    payload=payload,
                    workflow_state=WorkflowState.MISSING_REQUIRED_FIELDS,
                    missing_fields=missing,
                ),
            )

        # All fields present → ask for confirmation
        summary = self._format_payload_summary(intent, payload)
        response = f"{summary}\n\nConfirmas a criação?"

        return OrchestratorResponse(
            response=response,
            intent=intent,
            pending_action=PendingAction(
                action_id=str(uuid.uuid4()),
                tool=tool,
                payload=payload,
                workflow_state=WorkflowState.WAITING_CONFIRMATION,
                missing_fields=[],
            ),
        )

    # ===========================
    # HANDLE MISSING DATA REPLY
    # ===========================

    async def _handle_missing_data_reply(
        self, intent_result: IntentResult, conversation: ConversationState
    ) -> OrchestratorResponse:
        """User replied with missing data — merge into existing payload and re-evaluate."""
        pa = conversation.pending_action
        tool = pa.tool
        intent = tool  # tool name matches intent name in our system

        # Merge new entities into existing payload
        existing_payload = dict(pa.payload or {})
        new_entities = intent_result.entities

        merged_payload = self._merge_payload(intent, existing_payload, new_entities)

        # Re-check missing fields
        missing = self._find_missing_fields(intent, merged_payload)

        if missing:
            missing_labels = self._format_missing_fields(missing)
            return OrchestratorResponse(
                response=f"Obrigado! Ainda falta: {missing_labels}",
                intent=intent,
                pending_action=PendingAction(
                    action_id=pa.action_id,
                    tool=tool,
                    payload=merged_payload,
                    workflow_state=WorkflowState.MISSING_REQUIRED_FIELDS,
                    missing_fields=missing,
                ),
            )

        # All complete → ask confirmation
        summary = self._format_payload_summary(intent, merged_payload)
        return OrchestratorResponse(
            response=f"{summary}\n\nConfirmas a criação?",
            intent=intent,
            pending_action=PendingAction(
                action_id=pa.action_id,
                tool=tool,
                payload=merged_payload,
                workflow_state=WorkflowState.WAITING_CONFIRMATION,
                missing_fields=[],
            ),
        )

    # ===========================
    # SEARCH
    # ===========================

    async def _handle_search(self, intent: str, entities: Dict[str, Any]) -> OrchestratorResponse:
        """Handle search intents — execute and return results."""
        try:
            if intent == "SEARCH_PATIENT":
                name = entities.get("name") or entities.get("patient_name")
                species = entities.get("species")
                results = await self.php.search_patients(name=name, species=species)

                if not results:
                    return OrchestratorResponse(
                        response=f"Não encontrei nenhum paciente com esses critérios.",
                        intent=intent,
                        data=results,
                    )

                formatted = self._format_patient_list(results)
                return OrchestratorResponse(
                    response=f"Encontrei {len(results)} resultado(s):\n\n{formatted}",
                    intent=intent,
                    data=results,
                )

            elif intent == "SEARCH_OWNER":
                name = entities.get("name") or entities.get("owner_name")
                nif = entities.get("nif")
                results = await self.php.search_owners(name=name, nif=nif)

                if not results:
                    return OrchestratorResponse(
                        response=f"Não encontrei nenhum tutor com esses critérios.",
                        intent=intent,
                        data=results,
                    )

                formatted = self._format_owner_list(results)
                return OrchestratorResponse(
                    response=f"Encontrei {len(results)} resultado(s):\n\n{formatted}",
                    intent=intent,
                    data=results,
                )

        except PHPApiError as e:
            logger.error(f"PHP API error in search: {e}")
            return OrchestratorResponse(
                response="Erro ao pesquisar. Por favor tenta novamente.",
                intent=intent,
            )

    # ===========================
    # GET (history, appointments, owner_patients)
    # ===========================

    async def _handle_get(self, intent: str, entities: Dict[str, Any]) -> OrchestratorResponse:
        """Handle get/detail intents — resolve IDs and fetch data."""
        try:
            patient_id = entities.get("patient_id")
            patient_name = entities.get("patient_name") or entities.get("name")
            owner_id = entities.get("owner_id")
            owner_name = entities.get("owner_name") or entities.get("name")

            # Resolve patient by name if no ID
            if not patient_id and patient_name and intent in ("GET_PATIENT_HISTORY", "GET_APPOINTMENTS"):
                patient_id = await self._resolve_patient_id(patient_name)
                if not patient_id:
                    return OrchestratorResponse(
                        response=f"Não encontrei nenhum paciente com o nome '{patient_name}'. Podes verificar o nome?",
                        intent=intent,
                    )

            # Resolve owner by name if no ID
            if not owner_id and owner_name and intent == "GET_OWNER_PATIENTS":
                owner_id = await self._resolve_owner_id(owner_name)
                if not owner_id:
                    return OrchestratorResponse(
                        response=f"Não encontrei nenhum tutor com o nome '{owner_name}'. Podes verificar o nome?",
                        intent=intent,
                    )

            if intent == "GET_PATIENT_HISTORY":
                if not patient_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do paciente para consultar o histórico. Qual animal?",
                        intent=intent,
                    )
                history = await self.php.get_patient_history(patient_id)
                formatted = self._format_history(history, patient_name)
                return OrchestratorResponse(response=formatted, intent=intent, data=history)

            elif intent == "GET_APPOINTMENTS":
                if not patient_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do paciente para ver as consultas. Qual animal?",
                        intent=intent,
                    )
                appointments = await self.php.get_appointments_by_patient(patient_id)
                formatted = self._format_appointments(appointments, patient_name)
                return OrchestratorResponse(response=formatted, intent=intent, data=appointments)

            elif intent == "GET_OWNER_PATIENTS":
                if not owner_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do tutor. Qual tutor?",
                        intent=intent,
                    )
                patients = await self.php.get_patients_by_owner(owner_id)
                formatted = self._format_patient_list(patients)
                count = len(patients)
                return OrchestratorResponse(
                    response=f"O tutor tem {count} animal(is):\n\n{formatted}" if patients else "Este tutor não tem animais registados.",
                    intent=intent,
                    data=patients,
                )

        except PHPApiError as e:
            logger.error(f"PHP API error in get: {e}")
            return OrchestratorResponse(
                response="Erro ao consultar os dados. Por favor tenta novamente.",
                intent=intent,
            )

    # ===========================
    # HELPER: Resolve IDs by name
    # ===========================

    async def _resolve_patient_id(self, name: str) -> Optional[int]:
        """Search for a patient by name and return its ID (first match)."""
        results = await self.php.search_patients(name=name)
        if results:
            return results[0].get("id")
        return None

    async def _resolve_owner_id(self, name: str) -> Optional[int]:
        """Search for an owner by name and return its ID (first match)."""
        results = await self.php.search_owners(name=name)
        if results:
            return results[0].get("id")
        return None

    # ===========================
    # HELPER: Build/validate payloads
    # ===========================

    def _build_payload(self, intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Build a structured payload from entities based on intent.

        Normalizes species/breed values using local fuzzy matching.
        """
        if intent == "CREATE_OWNER_AND_PATIENT":
            owner_data = entities.get("owner", {})
            patient_data = entities.get("patient", {})

            # Sometimes entities come flat
            if not owner_data and not patient_data:
                owner_data = {
                    k: v for k, v in entities.items()
                    if k in ("name", "nif", "phone_number", "phone_number2", "email")
                    and "owner" not in str(entities.get("_source", ""))
                }
                patient_data = {
                    k: v for k, v in entities.items()
                    if k in ("name", "species", "breed", "weight", "birth_date", "microchip")
                }

            payload = {"owner": owner_data, "patient": patient_data}

        elif intent == "CREATE_OWNER":
            payload = {k: v for k, v in entities.items() if v is not None}

        elif intent == "CREATE_PATIENT":
            payload = {k: v for k, v in entities.items() if v is not None}

        elif intent == "ADD_VACCINES":
            payload = {k: v for k, v in entities.items() if v is not None}

        else:
            payload = entities

        # Normalize species/breed using local fuzzy matching (zero tokens)
        return normalize_entities(payload)

    def _find_missing_fields(self, intent: str, payload: Dict[str, Any]) -> List[str]:
        """Check which required fields are missing from the payload."""
        required = REQUIRED_FIELDS_MAP.get(intent, [])
        missing = []

        for field in required:
            if "." in field:
                # Nested field: "owner.name"
                parts = field.split(".")
                obj = payload
                found = True
                for part in parts:
                    if isinstance(obj, dict) and part in obj and obj[part]:
                        obj = obj[part]
                    else:
                        found = False
                        break
                if not found:
                    missing.append(field)
            else:
                value = payload.get(field)
                if not value and value != 0:
                    missing.append(field)

        return missing

    def _merge_payload(
        self, intent: str, existing: Dict[str, Any], new_entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge new entities into existing payload."""
        if intent == "CREATE_OWNER_AND_PATIENT":
            # Merge nested owner/patient
            new_owner = new_entities.get("owner", {})
            new_patient = new_entities.get("patient", {})

            # Also handle flat entities as updates
            flat_owner_fields = {"name", "nif", "phone_number", "phone_number2", "email"}
            flat_patient_fields = {"name", "species", "breed", "weight", "birth_date", "microchip"}

            owner = dict(existing.get("owner", {}))
            patient = dict(existing.get("patient", {}))

            # Merge from nested
            for k, v in new_owner.items():
                if v:
                    owner[k] = v
            for k, v in new_patient.items():
                if v:
                    patient[k] = v

            # Merge from flat (with prefix hints)
            for k, v in new_entities.items():
                if k in flat_owner_fields and v:
                    owner.setdefault(k, v)
                elif k in flat_patient_fields and v:
                    patient.setdefault(k, v)

            return {"owner": owner, "patient": patient}

        else:
            # Simple flat merge
            merged = dict(existing)
            for k, v in new_entities.items():
                if v is not None and v != "":
                    merged[k] = v
            return merged

    # ===========================
    # HELPER: Format output
    # ===========================

    def _format_missing_fields(self, missing: List[str]) -> str:
        """Format missing fields list into human-readable Portuguese."""
        labels = {
            "owner.name": "nome do tutor",
            "owner.nif": "NIF do tutor",
            "patient.name": "nome do animal",
            "name": "nome",
            "nif": "NIF",
            "owner": "ID do tutor (ou nome para pesquisar)",
            "patient_id": "ID do paciente",
            "vaccines": "lista de vacinas",
        }
        formatted = [labels.get(f, f) for f in missing]
        return ", ".join(formatted)

    def _format_payload_summary(self, intent: str, payload: Dict[str, Any]) -> str:
        """Format a payload into a human-readable summary."""
        if intent == "CREATE_OWNER_AND_PATIENT":
            owner = payload.get("owner", {})
            patient = payload.get("patient", {})
            lines = ["**Dados para criar:**", ""]
            lines.append(f"**Tutor:** {owner.get('name', '?')}")
            if owner.get("nif"):
                lines.append(f"  NIF: {owner['nif']}")
            if owner.get("phone_number"):
                lines.append(f"  Telefone: {owner['phone_number']}")
            if owner.get("email"):
                lines.append(f"  Email: {owner['email']}")
            lines.append("")
            lines.append(f"**Animal:** {patient.get('name', '?')}")
            if patient.get("species"):
                lines.append(f"  Espécie: {patient['species']}")
            if patient.get("breed"):
                lines.append(f"  Raça: {patient['breed']}")
            if patient.get("birth_date"):
                lines.append(f"  Data nascimento: {patient['birth_date']}")
            if patient.get("weight"):
                lines.append(f"  Peso: {patient['weight']}kg")
            if patient.get("microchip"):
                lines.append(f"  Microchip: {patient['microchip']}")
            return "\n".join(lines)

        elif intent == "CREATE_OWNER":
            lines = [f"**Tutor:** {payload.get('name', '?')}"]
            if payload.get("nif"):
                lines.append(f"  NIF: {payload['nif']}")
            if payload.get("phone_number"):
                lines.append(f"  Telefone: {payload['phone_number']}")
            if payload.get("email"):
                lines.append(f"  Email: {payload['email']}")
            return "\n".join(lines)

        elif intent == "CREATE_PATIENT":
            lines = [f"**Animal:** {payload.get('name', '?')}"]
            if payload.get("species"):
                lines.append(f"  Espécie: {payload['species']}")
            if payload.get("breed"):
                lines.append(f"  Raça: {payload['breed']}")
            if payload.get("owner"):
                lines.append(f"  Tutor ID: {payload['owner']}")
            return "\n".join(lines)

        elif intent == "ADD_VACCINES":
            lines = [f"**Vacinas para paciente ID {payload.get('patient_id', '?')}:**"]
            for v in payload.get("vaccines", []):
                name = v.get("name", "?")
                date = v.get("date", "")
                lines.append(f"  - {name}" + (f" ({date})" if date else ""))
            return "\n".join(lines)

        return str(payload)

    def _format_patient_list(self, patients: List[Dict[str, Any]]) -> str:
        """Format a list of patients for display."""
        if not patients:
            return "Nenhum resultado."
        lines = []
        for p in patients[:10]:  # Limit display to 10
            name = p.get("name", "?")
            species = p.get("species", "")
            breed = p.get("breed", "")
            owner_name = p.get("ownerName", "")
            line = f"- **{name}**"
            if species:
                line += f" ({species}"
                if breed:
                    line += f", {breed}"
                line += ")"
            if owner_name:
                line += f" — Tutor: {owner_name}"
            lines.append(line)
        if len(patients) > 10:
            lines.append(f"  ... e mais {len(patients) - 10} resultados")
        return "\n".join(lines)

    def _format_owner_list(self, owners: List[Dict[str, Any]]) -> str:
        """Format a list of owners for display."""
        if not owners:
            return "Nenhum resultado."
        lines = []
        for o in owners[:10]:
            name = o.get("name", "?")
            nif = o.get("nif", "")
            phone = o.get("phone_number", "")
            line = f"- **{name}**"
            if nif:
                line += f" (NIF: {nif})"
            if phone:
                line += f" — Tel: {phone}"
            lines.append(line)
        return "\n".join(lines)

    def _format_history(self, history: List[Dict[str, Any]], patient_name: Optional[str] = None) -> str:
        """Format patient clinical history."""
        name = patient_name or "paciente"
        if not history:
            return f"O {name} não tem histórico clínico registado."

        lines = [f"**Histórico clínico de {name}:**", ""]
        for entry in history[:20]:  # Limit
            date = entry.get("date", "?")
            entry_type = entry.get("type", "consulta")
            symptoms = entry.get("symptoms", "")
            diagnosis = entry.get("presumptuous_diagnosis", "")

            line = f"- [{date}] {entry_type}"
            if symptoms:
                line += f" — Sintomas: {symptoms}"
            if diagnosis:
                line += f" | Diagnóstico: {diagnosis}"
            lines.append(line)

        return "\n".join(lines)

    def _format_appointments(self, appointments: List[Dict[str, Any]], patient_name: Optional[str] = None) -> str:
        """Format patient appointments."""
        name = patient_name or "paciente"
        if not appointments:
            return f"O {name} não tem consultas registadas."

        lines = [f"**Consultas de {name}:**", ""]
        for apt in appointments[:15]:
            date = apt.get("date", "?")
            symptoms = apt.get("symptoms", "")
            diagnosis = apt.get("presumptuous_diagnosis", "")

            line = f"- [{date}]"
            if symptoms:
                line += f" Sintomas: {symptoms}"
            if diagnosis:
                line += f" → {diagnosis}"
            lines.append(line)

        return "\n".join(lines)
