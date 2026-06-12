import os
from typing import Any, Dict, List
from app.providers.base import ModelProvider
import httpx

GEMINI_API_URL = os.getenv("GEMINI_API_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class GeminiAdapter(ModelProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.base_url = base_url or GEMINI_API_URL

    async def chat(self, messages: List[Dict[str, Any]], model: str = "gemini") -> Dict[str, Any]:
        """
        Minimal Gemini adapter stub. It expects a HTTP endpoint at GEMINI_API_URL
        that accepts POST {messages, model} and returns a JSON similar to OpenAI.

        If no GEMINI_API_URL is configured, raise an error to avoid silent failures.
        """
        if not self.base_url:
            raise RuntimeError("GEMINI_API_URL not configured for GeminiAdapter")

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"model": model, "messages": messages}
        async with httpx.AsyncClient() as client:
            r = await client.post(self.base_url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
