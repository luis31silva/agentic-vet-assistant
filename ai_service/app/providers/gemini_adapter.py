import os
import base64
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
        system_instruction = "" 

        for msg in messages:
            role = msg.get("role", "user")
            content_text = msg.get("content", "")
            images = msg.get("images", [])

            if role == "system":
                system_instruction = content_text
            else:
                gemini_role = "model" if role == "assistant" else "user"
                parts = []

                if content_text:
                    parts.append(self.types.Part.from_text(text=content_text))

                # Processar imagens Base64 com lógica robusta
                for img_b64 in images:
                    try:
                        # 1. Identificar o tipo MIME e limpar o prefixo
                        mime_type = "image/jpeg" # Predefinição segura
                        clean_b64 = img_b64
                        
                        if img_b64.startswith("data:"):
                            # Formato: data:image/png;base64,iVBORw0KGgo...
                            # Separa no header e no corpo
                            header, clean_b64 = img_b64.split(",", 1)
                            # Extrai o mime type do header (ex: data:image/png;base64 -> image/png)
                            mime_type = header.split(":")[1].split(";")[0]
                        
                        # 2. Descodificar a string limpa para bytes puros
                        # Adicionamos 'validate=True' para garantir que é um base64 válido
                        img_bytes = base64.b64decode(clean_b64, validate=True)
                        
                        # 3. Adicionar a part multimédia
                        parts.append(
                            self.types.Part.from_bytes(
                                data=img_bytes,
                                mime_type=mime_type
                            )
                        )
                        logger.info(f"Imagem processada com sucesso: {mime_type} ({len(img_bytes)} bytes)")
                        
                    except Exception as e:
                        logger.error(f"Falha ao processar imagem Base64. A imagem será ignorada. Erro: {e}")

                if not parts:
                    parts.append(self.types.Part.from_text(text=""))

                formatted_contents.append(
                    self.types.Content(
                        role=gemini_role,
                        parts=parts
                    )
                )

        config_kwargs = {"response_mime_type": "application/json"}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        kwargs = {
            "model": model_name,
            "contents": formatted_contents,
            "config": self.types.GenerateContentConfig(**config_kwargs)
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