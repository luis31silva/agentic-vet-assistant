import json
from typing import Any, Dict, List

from loguru import logger

from app.providers.factory import get_model_provider
from app.schemas.models import IntentResult
from app.utils.image_processor import process_images


VALID_INTENTS = [
    "CREATE_OWNER_AND_PATIENT",
    "CREATE_OWNER",
    "CREATE_PATIENT",
    "ADD_VACCINES",
    "SEARCH_PATIENT",
    "SEARCH_OWNER",
    "GET_PATIENT_HISTORY",
    "GET_APPOINTMENTS",
    "GET_OWNER_PATIENTS",
    "CLINICAL_ADVICE",
    "CANCEL_ACTION",
    "CHAT",
]

SYSTEM_PROMPT = """És um assistente profissional de medicina veterinária numa clínica. A tua tarefa é classificar a mensagem do utilizador num dos intents disponíveis e extrair entidades relevantes.

## Intents disponíveis:

- **CREATE_OWNER_AND_PATIENT**: O utilizador quer registar um animal novo E o seu tutor (dono). Usa quando menciona dados do animal e do tutor em conjunto, ou quando envia imagens com informação de ambos.
- **CREATE_OWNER**: O utilizador quer registar apenas um tutor novo (sem animal).
- **CREATE_PATIENT**: O utilizador quer registar apenas um animal novo. O tutor já existe no sistema.
- **ADD_VACCINES**: O utilizador quer registar vacinas para um animal existente.
- **SEARCH_PATIENT**: O utilizador quer pesquisar ou consultar informação sobre um animal (por nome, espécie, etc.).
- **SEARCH_OWNER**: O utilizador quer pesquisar ou consultar informação sobre um tutor (por nome, NIF, etc.).
- **GET_PATIENT_HISTORY**: O utilizador quer ver o histórico clínico completo de um animal.
- **GET_APPOINTMENTS**: O utilizador quer ver as consultas de um animal.
- **GET_OWNER_PATIENTS**: O utilizador quer ver todos os animais de um tutor.
- **CLINICAL_ADVICE**: O utilizador pede conselhos clínicos, diagnósticos diferenciais, ou recomendações de tratamento para sintomas específicos de um animal.
- **CANCEL_ACTION**: O utilizador quer cancelar a ação em curso.
- **CHAT**: Conversa geral — saudações, perguntas genéricas sobre veterinária, agradecimentos, ou qualquer coisa que não se enquadre nos outros intents.

## Regras de classificação:

1. Se a mensagem contém imagens com dados de animal E tutor → CREATE_OWNER_AND_PATIENT
2. Se o utilizador menciona "adicionar", "registar", "criar" um animal com dados do tutor → CREATE_OWNER_AND_PATIENT
3. Se o utilizador só quer criar o animal e já menciona/conhece o tutor → CREATE_PATIENT
4. Se pergunta "mostra", "quais", "como está", "histórico" → usa o intent de consulta apropriado
5. Se pede conselhos sobre sintomas específicos de um animal identificado → CLINICAL_ADVICE
6. Se é saudação, agradecimento, pergunta genérica sobre saúde animal → CHAT
7. Se o utilizador diz "não", "cancela", "esquece" no contexto de uma ação pendente → CANCEL_ACTION

## Extração de entidades por intent:

- **CREATE_OWNER_AND_PATIENT**: extrair `owner: {name, nif, phone_number, email}` e `patient: {name, species, breed, weight, birth_date, microchip}`
- **CREATE_OWNER**: extrair `owner: {name, nif, phone_number, phone_number2, email}`
- **CREATE_PATIENT**: extrair `patient: {name, species, breed, weight, birth_date, microchip}` e `owner_name` ou `owner_id` se mencionado
- **ADD_VACCINES**: extrair `patient_name` ou `patient_id`, e `vaccines: [{name, date}]`
- **SEARCH_PATIENT**: extrair `name`, `species`, `breed`
- **SEARCH_OWNER**: extrair `name`, `nif`
- **GET_PATIENT_HISTORY**: extrair `patient_name` ou `patient_id`
- **GET_APPOINTMENTS**: extrair `patient_name` ou `patient_id`
- **GET_OWNER_PATIENTS**: extrair `owner_name` ou `owner_id`
- **CLINICAL_ADVICE**: extrair `patient_name` ou `patient_id`, `symptoms`
- **CHAT**: extrair nada de especial

## Formato de resposta (JSON obrigatório):

```json
{
  "intent": "INTENT_NAME",
  "confidence": 0.95,
  "entities": { ... },
  "response": "Texto de resposta para o utilizador (obrigatório para CHAT, opcional para outros)"
}
```

## Regras adicionais:
- Responde SEMPRE em Português de Portugal.
- Se recebes imagens, analisa-as e extrai toda a informação relevante para as entities.
- O campo `response` é OBRIGATÓRIO quando o intent é CHAT.
- Para intents de criação, inclui no `response` um resumo do que encontraste.
- Sê conciso e profissional nas respostas.
"""


class IntentService:
    def __init__(self):
        self.model = get_model_provider()

    async def classify(self, message: str, images: List[str], conversation) -> IntentResult:
        """Classify user message into an intent and extract entities.

        Args:
            message: User's text message
            images: List of base64-encoded images
            conversation: ConversationState with history and pending_action

        Returns:
            IntentResult with intent, confidence, entities, and optional response
        """
        # Compress images before sending to LLM
        compressed_images = process_images(images) if images else []

        # Build conversation context
        history_summary = ""
        if conversation and conversation.history:
            # Include last 6 messages for context
            recent = conversation.history[-6:]
            history_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    history_lines.append(f"{role}: {content}")
            history_summary = "\n".join(history_lines)

        # Include pending action context if exists
        pending_context = ""
        if conversation and conversation.pending_action:
            pa = conversation.pending_action
            pending_context = (
                f"\n[CONTEXTO: Existe uma ação pendente - Tool: {pa.tool}, "
                f"Estado: {pa.workflow_state}, Campos em falta: {pa.missing_fields}]"
            )

        user_content = f"Mensagem: {message}"
        if history_summary:
            user_content += f"\n\nHistórico recente:\n{history_summary}"
        if pending_context:
            user_content += pending_context

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content, "images": compressed_images},
        ]

        try:
            resp = await self.model.chat(messages)
            choices = resp.get("choices", [])

            if not choices:
                logger.warning("LLM returned no choices")
                return IntentResult(intent="CHAT", confidence=0.5, entities={}, response="Desculpa, não consegui processar. Podes repetir?")

            content = choices[0].get("message", {}).get("content", "")

            # Parse JSON response from LLM
            result = self._parse_response(content, message)
            return result

        except Exception as e:
            logger.exception(f"Error in intent classification: {e}")
            return IntentResult(
                intent="CHAT",
                confidence=0.0,
                entities={},
                response="Ocorreu um erro ao processar o teu pedido. Podes tentar novamente?",
            )

    def _parse_response(self, content: str, original_message: str) -> IntentResult:
        """Parse LLM JSON response into IntentResult."""
        # Try to extract JSON from response (handle markdown code blocks)
        json_str = content.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)

            intent = (data.get("intent") or "CHAT").upper()

            # Validate intent is in our list
            if intent not in VALID_INTENTS:
                logger.warning(f"LLM returned invalid intent '{intent}', falling back to CHAT")
                intent = "CHAT"

            confidence = float(data.get("confidence", 0.8))
            entities = data.get("entities", {})
            response = data.get("response", "")

            # Ensure CHAT always has a response
            if intent == "CHAT" and not response:
                response = "Em que posso ajudar?"

            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                response=response,
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}. Raw: {content[:200]}")
            # Fallback: try keyword-based classification
            return self._fallback_classify(original_message, content)

    def _fallback_classify(self, message: str, llm_response: str) -> IntentResult:
        """Fallback classification based on keywords when LLM JSON parsing fails."""
        text = message.lower()

        # Check for cancel
        if any(w in text for w in ["cancela", "não", "esquece", "anula"]):
            return IntentResult(intent="CANCEL_ACTION", confidence=0.7, entities={})

        # Check for search/query patterns
        if any(w in text for w in ["mostra", "procura", "busca", "encontra", "pesquisa"]):
            if any(w in text for w in ["histórico", "historial", "clínico"]):
                return IntentResult(intent="GET_PATIENT_HISTORY", confidence=0.7, entities={})
            if any(w in text for w in ["consulta", "consultas"]):
                return IntentResult(intent="GET_APPOINTMENTS", confidence=0.7, entities={})
            if any(w in text for w in ["animal", "animais", "paciente"]):
                return IntentResult(intent="SEARCH_PATIENT", confidence=0.7, entities={})
            if any(w in text for w in ["tutor", "dono", "proprietário"]):
                return IntentResult(intent="SEARCH_OWNER", confidence=0.7, entities={})

        # Check for creation patterns
        if any(w in text for w in ["adiciona", "registar", "criar", "novo", "nova"]):
            if any(w in text for w in ["vacina", "vacinas"]):
                return IntentResult(intent="ADD_VACCINES", confidence=0.7, entities={})
            if any(w in text for w in ["paciente", "animal"]) and any(w in text for w in ["tutor", "dono"]):
                return IntentResult(intent="CREATE_OWNER_AND_PATIENT", confidence=0.7, entities={})
            if any(w in text for w in ["tutor", "dono", "proprietário"]):
                return IntentResult(intent="CREATE_OWNER", confidence=0.7, entities={})
            if any(w in text for w in ["paciente", "animal"]):
                return IntentResult(intent="CREATE_PATIENT", confidence=0.7, entities={})

        # Default to CHAT with whatever the LLM said as response
        response = llm_response if llm_response else "Em que posso ajudar?"
        return IntentResult(intent="CHAT", confidence=0.5, entities={}, response=response)
