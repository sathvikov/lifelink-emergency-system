from __future__ import annotations

from fastapi import HTTPException


class AmbulanceService:
    def __init__(self) -> None:
        self._modules = {
            "assignments": {
                "title": "Assignments",
                "description": "Active dispatches and queued calls.",
                "highlights": [
                    {"label": "Active", "value": 2},
                    {"label": "Queued", "value": 3},
                    {"label": "Avg ETA", "value": "8 min"},
                ],
            },
            "live-tracking": {
                "title": "Live Tracking",
                "description": "Real-time vehicle location and telemetry.",
                "highlights": [
                    {"label": "In Transit", "value": 3},
                    {"label": "On Scene", "value": 1},
                    {"label": "Updates", "value": "Live"},
                ],
            },
            "patient-info": {
                "title": "Patient Info",
                "description": "Patient vitals and status updates.",
                "highlights": [
                    {"label": "Critical", "value": 1},
                    {"label": "Stable", "value": 2},
                    {"label": "Last Update", "value": "1 min ago"},
                ],
            },
            "navigation": {
                "title": "Navigation",
                "description": "Route guidance and optimization.",
                "highlights": [
                    {"label": "Suggested ETA", "value": "9 min"},
                    {"label": "Traffic", "value": "Medium"},
                    {"label": "Backup Route", "value": "10 min"},
                ],
            },
            "emergency-status": {
                "title": "Emergency Status",
                "description": "Severity flags and escalation state.",
                "highlights": [
                    {"label": "Critical", "value": 1},
                    {"label": "High", "value": 2},
                    {"label": "Escalations", "value": 1},
                ],
            },
            "history": {
                "title": "History",
                "description": "Completed missions and response history.",
                "highlights": [
                    {"label": "Completed", "value": 5},
                    {"label": "Avg Response", "value": "9 min"},
                    {"label": "Total Missions", "value": 128},
                ],
            },
        }

    def list_modules(self) -> dict:
        modules = [
            {"key": key, "title": value["title"], "description": value["description"]}
            for key, value in self._modules.items()
        ]
        return {"modules": modules}

    def get_module(self, module_key: str) -> dict:
        module = self._modules.get(module_key)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"key": module_key, **module}
