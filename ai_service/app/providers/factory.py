import os
from typing import Any
from app.providers.base import ModelProvider
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.gemini_adapter import GeminiAdapter


def get_model_provider() -> ModelProvider:
    """Return a ModelProvider implementation based on env var LLM_PROVIDER.

    Supported values: 'openai' (default), 'gemini'
    """
    p = os.getenv("LLM_PROVIDER", "openai").lower()
    if p == "gemini":
        return GeminiAdapter()
    # fallback to openai
    return OpenAIAdapter()
