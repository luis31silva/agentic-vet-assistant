import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

PHP_API_URL = os.getenv("PHP_API_URL", "http://localhost:8000/api")

# Timeouts
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 1


class PHPApiError(Exception):
    """Raised when PHP API returns an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PHP API error {status_code}: {detail}")


class PHPApiClient:
    """HTTP client for the PHP backend API.

    Supports Bearer token authentication and covers all endpoints
    needed by the AI orchestrator (read + create, no delete).
    """

    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.base = base_url or PHP_API_URL
        self.auth_token = auth_token

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute an HTTP request with retry logic."""
        url = f"{self.base}{path}"
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json,
                        params=params,
                        headers=self._headers(),
                    )

                    if response.status_code >= 400:
                        detail = response.text
                        try:
                            error_json = response.json()
                            detail = error_json.get("message", error_json.get("erro", response.text))
                        except Exception:
                            pass

                        # Don't retry client errors (4xx)
                        if response.status_code < 500:
                            raise PHPApiError(response.status_code, detail)

                        # Retry server errors (5xx)
                        if attempt < MAX_RETRIES:
                            logger.warning(
                                f"PHP API 5xx on {method} {path} (attempt {attempt + 1}): {detail}"
                            )
                            last_error = PHPApiError(response.status_code, detail)
                            continue
                        raise PHPApiError(response.status_code, detail)

                    # Parse JSON response
                    if response.status_code == 204:
                        return {}
                    return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"Timeout on {method} {path} (attempt {attempt + 1})")
                    continue
                raise PHPApiError(504, f"Timeout connecting to PHP API: {path}")

            except httpx.ConnectError as e:
                raise PHPApiError(503, f"Cannot connect to PHP API at {self.base}")

            except PHPApiError:
                raise

            except Exception as e:
                logger.error(f"Unexpected error calling PHP API: {e}")
                raise PHPApiError(500, f"Unexpected error: {str(e)}")

        # Should not reach here, but just in case
        if last_error:
            raise last_error

    # ===========================
    # OWNERS
    # ===========================

    async def get_owners(self) -> List[Dict[str, Any]]:
        """List all owners."""
        return await self._request("GET", "/owners")

    async def get_owner_by_id(self, owner_id: int) -> Dict[str, Any]:
        """Get a single owner by ID."""
        return await self._request("GET", f"/owners/{owner_id}")

    async def create_owner(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new owner. Returns {message, id}."""
        return await self._request("POST", "/owners", json=payload)

    # ===========================
    # PATIENTS
    # ===========================

    async def get_patients(self) -> List[Dict[str, Any]]:
        """List all patients."""
        return await self._request("GET", "/patients")

    async def get_patient_by_id(self, patient_id: int) -> Dict[str, Any]:
        """Get a single patient by ID."""
        return await self._request("GET", f"/patients/{patient_id}")

    async def get_patients_by_owner(self, owner_id: int) -> List[Dict[str, Any]]:
        """List patients for a specific owner."""
        return await self._request("GET", f"/patients/owner/{owner_id}")

    async def get_patient_history(self, patient_id: int) -> List[Dict[str, Any]]:
        """Get full clinical history for a patient."""
        return await self._request("GET", f"/patients/history/{patient_id}")

    async def create_patient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new patient. Returns {message, id}."""
        return await self._request("POST", "/patients", json=payload)

    # ===========================
    # APPOINTMENTS
    # ===========================

    async def get_appointments(self) -> List[Dict[str, Any]]:
        """List all appointments."""
        return await self._request("GET", "/appointments")

    async def get_appointment_by_id(self, appointment_id: int) -> Dict[str, Any]:
        """Get a single appointment by ID."""
        return await self._request("GET", f"/appointments/{appointment_id}")

    async def get_appointments_by_patient(self, patient_id: int) -> List[Dict[str, Any]]:
        """List appointments for a specific patient."""
        return await self._request("GET", f"/appointments/patient/{patient_id}")

    async def create_appointment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new appointment. Returns {message, id}."""
        return await self._request("POST", "/appointments", json=payload)

    # ===========================
    # VACCINES / INVENTORY
    # ===========================

    async def get_inventory(self, inventory_type: str) -> List[Dict[str, Any]]:
        """List inventory items by type (vaccines, medications, etc.)."""
        return await self._request("GET", f"/inventory/{inventory_type}")

    async def add_vaccines(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add vaccines to a patient (via appointment creation)."""
        return await self._request("POST", "/appointments", json=payload)

    # ===========================
    # EVENTS
    # ===========================

    async def get_events(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List events (filtered by year/month or date)."""
        return await self._request("GET", "/events", params=params)

    async def create_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event."""
        return await self._request("POST", "/events", json=payload)

    # ===========================
    # SURGERIES
    # ===========================

    async def get_surgeries_by_patient(self, patient_id: int) -> List[Dict[str, Any]]:
        """List surgeries for a specific patient."""
        return await self._request("GET", f"/surgeries/patient/{patient_id}")

    # ===========================
    # HOSPITALIZATIONS
    # ===========================

    async def get_hospitalizations(self) -> List[Dict[str, Any]]:
        """List all hospitalizations."""
        return await self._request("GET", "/hospitalizations")

    async def get_hospitalization_by_id(self, hospitalization_id: int) -> Dict[str, Any]:
        """Get a single hospitalization by ID."""
        return await self._request("GET", f"/hospitalizations/{hospitalization_id}")

    # ===========================
    # INVOICES
    # ===========================

    async def get_invoices_by_owner(self, owner_id: int) -> List[Dict[str, Any]]:
        """List invoices for a specific owner."""
        return await self._request("GET", f"/invoices/owner/{owner_id}")

    # ===========================
    # SEARCH (convenience methods)
    # ===========================

    async def search_patients(self, name: Optional[str] = None, species: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search patients by name and/or species (local filtering)."""
        patients = await self.get_patients()
        results = patients

        if name:
            name_lower = name.lower()
            results = [p for p in results if name_lower in p.get("name", "").lower()]

        if species:
            species_lower = species.lower()
            results = [p for p in results if species_lower in (p.get("species") or "").lower()]

        return results

    async def search_owners(self, name: Optional[str] = None, nif: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search owners by name and/or NIF (local filtering)."""
        owners = await self.get_owners()
        results = owners

        if name:
            name_lower = name.lower()
            results = [o for o in results if name_lower in o.get("name", "").lower()]

        if nif:
            results = [o for o in results if nif in (o.get("nif") or "")]

        return results
