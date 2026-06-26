from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from app.schemas.models import ClinicalAdviceRequest
from app.services.clinical_advisor import ClinicalAdvisor

router = APIRouter()
advisor = ClinicalAdvisor()


@router.post("/")
async def clinical_advice(req: ClinicalAdviceRequest, request: Request):
    """Generate clinical advice based on patient symptoms and history.

    This endpoint is called from a dedicated button in the frontend
    during appointment creation. It fetches the patient's history
    and generates contextual clinical recommendations.

    Body:
        patient_id: int - ID of the patient
        symptoms: str - Current symptoms described by the vet
        appointment_context: str (optional) - Additional context

    Returns:
        { status: "ok", advice: "..." }
    """
    try:
        if not req.symptoms or not req.symptoms.strip():
            raise HTTPException(status_code=400, detail="Sintomas são obrigatórios.")

        if not req.patient_id:
            raise HTTPException(status_code=400, detail="ID do paciente é obrigatório.")

        # Extract auth token from the incoming request (forwarded from PHP)
        auth_token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ", 1)[1]

        logger.info(f"/clinical-advice for patient_id={req.patient_id}")

        advice = await advisor.advise(
            patient_id=req.patient_id,
            symptoms=req.symptoms,
            appointment_context=req.appointment_context,
            auth_token=auth_token,
        )

        return {"status": "ok", "advice": advice}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("clinical advice error")
        raise HTTPException(status_code=500, detail="Erro ao gerar conselhos clínicos.")
