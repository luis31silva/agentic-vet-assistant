from typing import Any, Dict, List, Optional

from loguru import logger

from app.schemas.models import (
    ConversationState,
    IntentResult,
    OrchestratorResponse,
)
from app.utils.php_api_client import PHPApiClient, PHPApiError


class Orchestrator:
    """Handles query/search intents that need to fetch data from the PHP API.

    Creation intents are NOT handled here — those just return entities
    to the frontend, which opens the appropriate form/modal.
    """

    def __init__(self, auth_token: Optional[str] = None):
        self.php = PHPApiClient(auth_token=auth_token)

    async def handle(
        self,
        intent_result: IntentResult,
        conversation: ConversationState,
        images: List[str] = None,
    ) -> OrchestratorResponse:
        """Route query intents to the appropriate handler."""
        intent = intent_result.intent
        entities = intent_result.entities

        logger.info(f"Orchestrator handling query: {intent}")

        if intent in ("SEARCH_PATIENT", "SEARCH_OWNER"):
            return await self._handle_search(intent, entities)

        elif intent in ("GET_PATIENT_HISTORY", "GET_APPOINTMENTS", "GET_OWNER_PATIENTS"):
            return await self._handle_get(intent, entities)

        # Fallback — should not reach here
        return OrchestratorResponse(
            response=intent_result.response or "",
            intent=intent,
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
                        response="Não encontrei nenhum paciente com esses critérios.",
                        intent=intent,
                        data=[],
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
                        response="Não encontrei nenhum tutor com esses critérios.",
                        intent=intent,
                        data=[],
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
                data=[],
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
                        response=f"Não encontrei nenhum paciente com o nome '{patient_name}'.",
                        intent=intent,
                        data=[],
                    )

            # Resolve owner by name if no ID
            if not owner_id and owner_name and intent == "GET_OWNER_PATIENTS":
                owner_id = await self._resolve_owner_id(owner_name)
                if not owner_id:
                    return OrchestratorResponse(
                        response=f"Não encontrei nenhum tutor com o nome '{owner_name}'.",
                        intent=intent,
                        data=[],
                    )

            if intent == "GET_PATIENT_HISTORY":
                if not patient_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do paciente para consultar o histórico.",
                        intent=intent,
                        data=[],
                    )
                history = await self.php.get_patient_history(patient_id)
                formatted = self._format_history(history, patient_name)
                return OrchestratorResponse(response=formatted, intent=intent, data=history)

            elif intent == "GET_APPOINTMENTS":
                if not patient_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do paciente para ver as consultas.",
                        intent=intent,
                        data=[],
                    )
                appointments = await self.php.get_appointments_by_patient(patient_id)
                formatted = self._format_appointments(appointments, patient_name)
                return OrchestratorResponse(response=formatted, intent=intent, data=appointments)

            elif intent == "GET_OWNER_PATIENTS":
                if not owner_id:
                    return OrchestratorResponse(
                        response="Preciso do nome ou ID do tutor.",
                        intent=intent,
                        data=[],
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
                data=[],
            )

    # ===========================
    # HELPERS
    # ===========================

    async def _resolve_patient_id(self, name: str) -> Optional[int]:
        results = await self.php.search_patients(name=name)
        if results:
            return results[0].get("id")
        return None

    async def _resolve_owner_id(self, name: str) -> Optional[int]:
        results = await self.php.search_owners(name=name)
        if results:
            return results[0].get("id")
        return None

    def _format_patient_list(self, patients: List[Dict[str, Any]]) -> str:
        if not patients:
            return "Nenhum resultado."
        lines = []
        for p in patients[:10]:
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
        name = patient_name or "paciente"
        if not history:
            return f"O {name} não tem histórico clínico registado."
        lines = [f"**Histórico clínico de {name}:**", ""]
        for entry in history[:20]:
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
