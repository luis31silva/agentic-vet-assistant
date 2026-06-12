from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.providers.ocr_provider import OCRProvider
from loguru import logger

router = APIRouter()
ocr = OCRProvider()


class ProcessDocumentsRequest(BaseModel):
    images: List[str]


@router.post("/")
async def process_documents(req: ProcessDocumentsRequest):
    try:
        texts = []
        for img in req.images:
            txt = await ocr.extract_text(img)
            texts.append({"image": img, "text": txt})
        return {"status": "ok", "results": texts}
    except Exception as e:
        logger.exception("ocr error")
        raise HTTPException(status_code=500, detail=str(e))
