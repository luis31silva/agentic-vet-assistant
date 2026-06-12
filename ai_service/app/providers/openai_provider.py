import os
from typing import Any, Dict, List
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or OPENAI_API_KEY

    async def chat(self, messages: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "temperature": 0}
        async with httpx.AsyncClient() as client:
            r = await client.post(OPENAI_URL, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
