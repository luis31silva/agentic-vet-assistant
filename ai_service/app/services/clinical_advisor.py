from typing import Any, Dict, List, Optional

from loguru import logger

from app.providers.factory import get_model_provider
from app.utils.php_api_client import PHPApiClient, PHPApiError


CLINICAL_SYSTEM_PROMPT = """És um assistente clínico veterinário especializado. O teu papel é ajudar o veterinário com sugestões de diagnóstico diferencial e recomendações clínicas.

## Contexto
Vais receber:
1. Dados do paciente (espécie, raça, idade, peso)
2. Histórico clínico (consultas anteriores, vacinas, cirurgias)
3. Sintomas atuais descritos pelo veterinário

## O que deves fazer:
1. **Diagnósticos diferenciais** — Lista os 3-5 diagnósticos mais prováveis, ordenados por probabilidade, com breve justificação
2. **Exames recomendados** — Sugere exames complementares relevantes
3. **Considerações** — Alertas baseados no histórico (interações, contra-indicações, padrões recorrentes)
4. **Abordagem terapêutica inicial** — Sugestões gerais de tratamento (se aplicável)

## Regras:
- Responde SEMPRE em Português de Portugal
- Sê conciso e profissional — o público-alvo são veterinários
- Considera a espécie, raça, idade e peso nas tuas sugestões (um diagnóstico que é comum em cães grandes pode ser raro em gatos)
- Se o histórico revelar padrões relevantes (ex: problema recorrente), menciona
- Termina SEMPRE com: "⚠️ Nota: Estas são sugestões baseadas em IA. O diagnóstico final e decisão terapêutica são da responsabilidade do médico veterinário."
"""


class ClinicalAdvisor:
    """Service that generates clinical advice based on patient context and symptoms."""

    def __init__(self):
        self.model = get_model_provider()

    async def advise(
        self,
        patient_id: int,
        symptoms: str,
        appointment_context: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> str:
        """Generate clinical advice for a patient.

        Args:
            patient_id: ID of the patient
            symptoms: Current symptoms described by the vet
            appointment_context: Optional additional context from the appointment
            auth_token: JWT token for PHP API authentication

        Returns:
            Clinical advice text in Portuguese
        """
        php = PHPApiClient(auth_token=auth_token)

        # Fetch patient data and history
        patient_data = await self._fetch_patient_data(php, patient_id)
        history_data = await self._fetch_patient_history(php, patient_id)

        # Build the context prompt
        context = self._build_context(patient_data, history_data, symptoms, appointment_context)

        # Call LLM
        messages = [
            {"role": "system", "content": CLINICAL_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            resp = await self.model.chat(messages)
            choices = resp.get("choices", [])

            if not choices:
                return "Não foi possível gerar recomendações neste momento. Tenta novamente."

            content = choices[0].get("message", {}).get("content", "")

            # Clean up JSON wrapping if the model returns it
            if content.startswith("{") or content.startswith('"'):
                import json
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        content = parsed.get("advice", parsed.get("response", str(parsed)))
                    elif isinstance(parsed, str):
                        content = parsed
                except (json.JSONDecodeError, ValueError):
                    pass

            return content

        except Exception as e:
            logger.exception(f"Error generating clinical advice: {e}")
            return "Ocorreu um erro ao gerar as recomendações clínicas. Por favor tenta novamente."

    async def _fetch_patient_data(self, php: PHPApiClient, patient_id: int) -> Dict[str, Any]:
        """Fetch patient basic data."""
        try:
            return await php.get_patient_by_id(patient_id)
        except PHPApiError as e:
            logger.warning(f"Could not fetch patient {patient_id}: {e}")
            return {}

    async def _fetch_patient_history(self, php: PHPApiClient, patient_id: int) -> List[Dict[str, Any]]:
        """Fetch patient clinical history (limited to last 10 entries for token efficiency)."""
        try:
            history = await php.get_patient_history(patient_id)
            # Limit to last 10 entries to control token usage
            return history[-10:] if len(history) > 10 else history
        except PHPApiError as e:
            logger.warning(f"Could not fetch history for patient {patient_id}: {e}")
            return []

    def _build_context(
        self,
        patient: Dict[str, Any],
        history: List[Dict[str, Any]],
        symptoms: str,
        appointment_context: Optional[str] = None,
    ) -> str:
        """Build the user prompt with all clinical context."""
        lines = []

        # Patient info
        lines.append("## Dados do Paciente")
        if patient:
            name = patient.get("name", "Desconhecido")
            species = patient.get("species", "Não especificada")
            breed = patient.get("breed", "Não especificada")
            weight = patient.get("weight")
            birth_date = patient.get("birth_date")
            age = patient.get("age")

            lines.append(f"- Nome: {name}")
            lines.append(f"- Espécie: {species}")
            lines.append(f"- Raça: {breed}")
            if weight:
                lines.append(f"- Peso: {weight}kg")
            if age:
                lines.append(f"- Idade: {age} anos")
            elif birth_date:
                lines.append(f"- Data de nascimento: {birth_date}")
        else:
            lines.append("- Dados do paciente não disponíveis")

        # History
        lines.append("")
        lines.append("## Histórico Clínico")
        if history:
            for entry in history:
                date = entry.get("date", "?")
                entry_type = entry.get("type", "consulta")
                entry_symptoms = entry.get("symptoms", "")
                diagnosis = entry.get("presumptuous_diagnosis", "")
                vaccines = entry.get("vaccines", [])

                line = f"- [{date}] {entry_type}"
                if entry_symptoms:
                    line += f" | Sintomas: {entry_symptoms}"
                if diagnosis:
                    line += f" | Diagnóstico: {diagnosis}"
                if vaccines:
                    vaccine_names = [v.get("name", "?") for v in vaccines] if isinstance(vaccines, list) else []
                    if vaccine_names:
                        line += f" | Vacinas: {', '.join(vaccine_names)}"
                lines.append(line)
        else:
            lines.append("- Sem histórico clínico registado")

        # Current symptoms
        lines.append("")
        lines.append("## Sintomas Atuais")
        lines.append(symptoms)

        # Additional context
        if appointment_context:
            lines.append("")
            lines.append("## Contexto adicional da consulta")
            lines.append(appointment_context)

        return "\n".join(lines)
