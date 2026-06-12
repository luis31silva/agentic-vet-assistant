from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ModelProvider(ABC):
    """Abstract interface for LLM providers.

    Implementations must accept a list of chat messages and return a provider
    response as a dict. The rest of the application will not depend on
    provider-specific SDKs.
    """

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], model: str = "") -> Dict[str, Any]:
        raise NotImplementedError()
