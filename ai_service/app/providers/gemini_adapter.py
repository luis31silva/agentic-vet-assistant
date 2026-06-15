import os
from typing import Any, Dict, List
from app.providers.base import ModelProvider
from loguru import logger

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiAdapter(ModelProvider):
    """Adapter que utiliza o novo SDK oficial google-genai para o Gemini."""

    def __init__(self, api_key: str | None = None, default_model: str | None = "gemini-2.5-flash"):
        self.api_key = api_key or GEMINI_API_KEY
        self.default_model = default_model or "gemini-2.5-flash"

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY não configurada no GeminiAdapter")

        try:
            from google import genai
            from google.genai import types
            self.types = types
            self.client = genai.Client(api_key=self.api_key)
        except ImportError as exc:
            raise RuntimeError(
                "SDK google-genai não disponível. Instale com: pip install google-genai"
            ) from exc

    async def chat(self, messages: List[Dict[str, Any]], model: str | None = None) -> Dict[str, Any]:
        model_name = model or self.default_model

        formatted_contents = []
        system_instruction = (
            "Tu és um assistente de uma clínica veterinária em Portugal. "
            "Sê cordial, profissional e eficiente. "
            "Se a mensagem do utilizador for apenas uma saudação (ex: 'Bom dia', 'Olá'), "
            "responde de forma amigável e pergunta como podes ajudar com o animal de estimação. "
            "Para outras questões, tenta identificar a intenção (ex: marcação de consulta, urgência, dúvida de medicação). "
            "Responde sempre em português de Portugal."
        )

        for msg in messages:
            role = msg.get("role", "user")
            content_text = msg.get("content", "")

            if role == "system":
                system_instruction = content_text
            else:
                gemini_role = "model" if role == "assistant" else "user"
                formatted_contents.append(
                    self.types.Content(
                        role=gemini_role,
                        parts=[self.types.Part.from_text(text=content_text)]
                    )
                )

        kwargs = {
            "model": model_name,
            "contents": formatted_contents,
            "config": self.types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            )
        }

        try:
            response = await self.client.aio.models.generate_content(**kwargs)
            text = response.text
        except Exception as e:
            logger.error(f"Erro na API do Gemini: {str(e)}")
            return {
                "choices": [{"message": {"role": "assistant", "content": '{"error": "Erro no serviço"}'}}]
            }

        return {
            "choices": [{"message": {"role": "assistant", "content": text}}]
        }