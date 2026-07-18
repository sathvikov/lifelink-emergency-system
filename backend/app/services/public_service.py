from __future__ import annotations

from fastapi import HTTPException


class PublicService:
    def __init__(self) -> None:
        self._modules = {
            "home": {
                "title": "LifeLink Home",
                "description": "Quick access to emergency and care actions.",
                "highlights": [
                    {"label": "Smart SOS", "value": "Ready"},
                    {"label": "Hospitals", "value": "Nearby"},
                    {"label": "Family", "value": "Monitored"},
                ],
            },
            "sos": {
                "title": "Smart SOS",
                "description": "One tap to dispatch ambulance, hospital, and family alerts.",
                "highlights": [
                    {"label": "Dispatch", "value": "Auto"},
                    {"label": "ETA", "value": "Live"},
                    {"label": "Hospital", "value": "Ranked"},
                ],
            },
            "hospital": {
                "title": "Find Hospital",
                "description": "Ranked hospitals with beds and ETA near you.",
                "highlights": [
                    {"label": "Beds", "value": "Live"},
                    {"label": "ETA", "value": "AI"},
                    {"label": "Distance", "value": "Closest"},
                ],
            },
            "health": {
                "title": "Quick Health Check",
                "description": "Vital-based risk score with clear next steps.",
                "highlights": [
                    {"label": "Risk", "value": "ML"},
                    {"label": "Vitals", "value": "Fast"},
                    {"label": "Summary", "value": "Simple"},
                ],
            },
            "donor": {
                "title": "Donor Match",
                "description": "Ranked donors using distance, urgency, availability.",
                "highlights": [
                    {"label": "Priority", "value": "Weighted"},
                    {"label": "Match", "value": "Instant"},
                    {"label": "Nearby", "value": "Yes"},
                ],
            },
            "family": {
                "title": "Family Monitoring",
                "description": "Lightweight monitoring for trusted contacts.",
                "highlights": [
                    {"label": "Members", "value": "Live"},
                    {"label": "Alerts", "value": "Shared"},
                    {"label": "Check-in", "value": "Simple"},
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
