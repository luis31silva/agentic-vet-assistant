from typing import Any, Dict

from loguru import logger

from app.tools.base import BaseTool
from app.schemas.models import CreateOwnerRequest, PatientData
from app.utils.php_api_client import PHPApiClient, PHPApiError


class CreateOwnerAndPatientTool(BaseTool):
    name = "CREATE_OWNER_AND_PATIENT"
    description = "Cria um tutor e o seu animal em conjunto."

    async def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate composite payload (owner + patient sections)."""
        errors = []

        owner_data = payload.get("owner", {})
        patient_data = payload.get("patient", {})

        # Validate owner
        try:
            CreateOwnerRequest(**owner_data)
        except Exception as e:
            if hasattr(e, "errors"):
                for err in e.errors():
                    field = "owner." + ".".join(str(loc) for loc in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    errors.append(f"{field}: {msg}")
            else:
                errors.append(f"owner: {str(e)}")

        # Validate patient (without owner field - it will be injected)
        try:
            PatientData(**patient_data)
        except Exception as e:
            if hasattr(e, "errors"):
                for err in e.errors():
                    field = "patient." + ".".join(str(loc) for loc in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    errors.append(f"{field}: {msg}")
            else:
                errors.append(f"patient: {str(e)}")

        if errors:
            return {"valid": False, "errors": errors}
        return {"valid": True, "errors": []}

    async def execute(self, payload: Dict[str, Any], php_client: PHPApiClient) -> Dict[str, Any]:
        """Create owner first, then patient with the owner's ID.

        Sequential execution:
        1. POST /owners → get owner_id
        2. POST /patients with owner=owner_id
        """
        owner_data = payload.get("owner", {})
        patient_data = payload.get("patient", {})

        # Step 1: Create owner
        try:
            owner_result = await php_client.create_owner(owner_data)
            owner_id = owner_result.get("id")
            logger.info(f"Owner created: ID={owner_id}, name={owner_data.get('name')}")
        except PHPApiError as e:
            logger.error(f"Failed to create owner in composite: {e}")
            if "nif" in e.detail.lower() or "duplicat" in e.detail.lower():
                return {
                    "success": False,
                    "message": f"Não foi possível criar o tutor: já existe um tutor com o NIF '{owner_data.get('nif')}'.",
                    "error": e.detail,
                }
            return {
                "success": False,
                "message": f"Erro ao criar o tutor: {e.detail}",
                "error": e.detail,
            }

        # Step 2: Create patient with owner_id
        patient_payload = dict(patient_data)
        patient_payload["owner"] = owner_id

        try:
            patient_result = await php_client.create_patient(patient_payload)
            patient_id = patient_result.get("id")
            logger.info(f"Patient created: ID={patient_id}, name={patient_data.get('name')}, owner_id={owner_id}")
        except PHPApiError as e:
            logger.error(f"Failed to create patient in composite (owner was created): {e}")
            return {
                "success": False,
                "message": (
                    f"O tutor '{owner_data.get('name')}' foi criado (ID: {owner_id}), "
                    f"mas ocorreu um erro ao criar o paciente: {e.detail}. "
                    f"Podes tentar criar o paciente separadamente."
                ),
                "owner_id": owner_id,
                "error": e.detail,
            }

        return {
            "success": True,
            "message": (
                f"Tutor '{owner_data.get('name')}' (ID: {owner_id}) e "
                f"paciente '{patient_data.get('name')}' (ID: {patient_id}) criados com sucesso!"
            ),
            "owner_id": owner_id,
            "patient_id": patient_id,
            "data": {"owner": owner_result, "patient": patient_result},
        }
