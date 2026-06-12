import os
from typing import Any, Dict, List
from app.providers.base import ModelProvider
from app.providers import openai_provider as _openai


class OpenAIAdapter(ModelProvider):
    def __init__(self, api_key: str | None = None):
        self.client = _openai.OpenAIProvider(api_key=api_key)

    async def chat(self, messages: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> Dict[str, Any]:
        return await self.client.chat(messages=messages, model=model)
