import os
from typing import Optional
import httpx

OCR_API_URL = os.getenv("OCR_API_URL")


class OCRProvider:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or OCR_API_URL

    async def extract_text(self, image_url: str) -> str:
        # Minimal stub: if OCR_API_URL is set, POST {image_url}, otherwise return empty string
        if not self.base_url:
            return ""
        async with httpx.AsyncClient() as client:
            r = await client.post(self.base_url, json={"image_url": image_url}, timeout=30)
            r.raise_for_status()
            data = r.json()
            return data.get("text", "")
