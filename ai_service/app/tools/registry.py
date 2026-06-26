from typing import Dict, Optional

from app.tools.base import BaseTool
from app.tools.create_owner_tool import CreateOwnerTool
from app.tools.create_patient_tool import CreatePatientTool
from app.tools.create_owner_and_patient_tool import CreateOwnerAndPatientTool
from app.tools.add_vaccines_tool import AddVaccinesTool
from app.tools.search_patient_tool import SearchPatientTool
from app.tools.search_owner_tool import SearchOwnerTool
from app.tools.get_patient_history_tool import GetPatientHistoryTool
from app.tools.get_appointments_tool import GetAppointmentsTool
from app.tools.get_owner_patients_tool import GetOwnerPatientsTool


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all built-in tools."""
        tools = [
            # Creation tools
            CreateOwnerTool(),
            CreatePatientTool(),
            CreateOwnerAndPatientTool(),
            AddVaccinesTool(),
            # Query tools
            SearchPatientTool(),
            SearchOwnerTool(),
            GetPatientHistoryTool(),
            GetAppointmentsTool(),
            GetOwnerPatientsTool(),
        ]
        for tool in tools:
            self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name (case-insensitive)."""
        return self._tools.get(name.upper())

    def list_tools(self) -> Dict[str, str]:
        """Return dict of tool_name → description."""
        return {name: tool.description for name, tool in self._tools.items()}


# Singleton instance
tool_registry = ToolRegistry()
