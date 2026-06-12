import os
from typing import Any, Dict
import httpx

PHP_API_URL = os.getenv("PHP_API_URL", "http://localhost:8000/api")


class PHPApiClient:
    def __init__(self, base_url: str = None):
        self.base = base_url or PHP_API_URL

    async def create_patient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/patients", json=payload, timeout=30)
            r.raise_for_status()
            return r.json()

    async def create_owner(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/owners", json=payload, timeout=30)
            r.raise_for_status()
            return r.json()

    async def add_vaccines(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/vaccines", json=payload, timeout=30)
            r.raise_for_status()
            return r.json()

    async def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base}/search", params=params, timeout=30)
            r.raise_for_status()
            return r.json()
