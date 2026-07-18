from __future__ import annotations

from fastapi import HTTPException


class GovernmentService:
    def __init__(self) -> None:
        self._modules = {
            "national_admin": {
                "country-dashboard": {
                    "title": "Country Dashboard",
                    "description": "National-level response overview.",
                    "highlights": [
                        {"label": "Regions", "value": 12},
                        {"label": "Critical Alerts", "value": 8},
                        {"label": "Coverage", "value": "94%"},
                    ],
                },
                "emergency-heatmap": {
                    "title": "Emergency Heatmap",
                    "description": "National emergency hotspots and clusters.",
                    "highlights": [
                        {"label": "Hotspots", "value": 5},
                        {"label": "High Risk", "value": 2},
                        {"label": "Trend", "value": "Rising"},
                    ],
                },
                "resource-allocation": {
                    "title": "Resource Allocation",
                    "description": "Allocation of national resources and units.",
                    "highlights": [
                        {"label": "Active Deployments", "value": 14},
                        {"label": "Stock Coverage", "value": "88%"},
                        {"label": "Requests", "value": 6},
                    ],
                },
                "policy-insights": {
                    "title": "Policy Insights",
                    "description": "Policy impact and AI insight summaries.",
                    "highlights": [
                        {"label": "Policies", "value": 4},
                        {"label": "Impact Score", "value": "High"},
                        {"label": "Recommendations", "value": 3},
                    ],
                },
            },
            "state_admin": {
                "state-dashboard": {
                    "title": "State Dashboard",
                    "description": "State operations summary and alerts.",
                    "highlights": [
                        {"label": "Districts", "value": 8},
                        {"label": "Active Alerts", "value": 12},
                        {"label": "Response", "value": "88%"},
                    ],
                },
                "hospital-monitoring": {
                    "title": "Hospital Monitoring",
                    "description": "Monitor hospital status and capacity.",
                    "highlights": [
                        {"label": "Hospitals", "value": 38},
                        {"label": "ICU Alerts", "value": 4},
                        {"label": "Transfers", "value": 3},
                    ],
                },
                "reports": {
                    "title": "Reports",
                    "description": "State-level reports and compliance summaries.",
                    "highlights": [
                        {"label": "Reports", "value": 8},
                        {"label": "Pending", "value": 3},
                        {"label": "Approved", "value": 5},
                    ],
                },
            },
            "district_admin": {
                "district-emergencies": {
                    "title": "District Emergencies",
                    "description": "District-level emergency coordination.",
                    "highlights": [
                        {"label": "Active", "value": 6},
                        {"label": "High Priority", "value": 2},
                        {"label": "Avg ETA", "value": "9 min"},
                    ],
                },
                "ambulance-tracking": {
                    "title": "Ambulance Tracking",
                    "description": "Track district ambulance positions.",
                    "highlights": [
                        {"label": "In Transit", "value": 4},
                        {"label": "Available", "value": 5},
                        {"label": "Delayed", "value": 1},
                    ],
                },
            },
            "supervisory_authority": {
                "hospital-audits": {
                    "title": "Hospital Audits",
                    "description": "Audit schedules and findings.",
                    "highlights": [
                        {"label": "Audits", "value": 24},
                        {"label": "Findings", "value": 6},
                        {"label": "Resolved", "value": 18},
                    ],
                },
                "compliance-monitoring": {
                    "title": "Compliance Monitoring",
                    "description": "Compliance scorecards and risk flags.",
                    "highlights": [
                        {"label": "Compliance", "value": "92%"},
                        {"label": "Risk Flags", "value": 4},
                        {"label": "Follow-ups", "value": 3},
                    ],
                },
            },
        }

    def list_modules(self, sub_role: str | None) -> dict:
        module_set = self._modules.get(sub_role or "", {})
        if not module_set:
            raise HTTPException(status_code=400, detail="Government subRole required")
        modules = [
            {"key": key, "title": value["title"], "description": value["description"]}
            for key, value in module_set.items()
        ]
        return {"subRole": sub_role, "modules": modules}

    def get_module(self, sub_role: str | None, module_key: str) -> dict:
        module_set = self._modules.get(sub_role or "", {})
        if not module_set:
            raise HTTPException(status_code=400, detail="Government subRole required")
        module = module_set.get(module_key)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"key": module_key, **module}
