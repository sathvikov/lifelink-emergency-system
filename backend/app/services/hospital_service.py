from __future__ import annotations

from fastapi import HTTPException


class HospitalService:
    def __init__(self) -> None:
        self._modules = {
            "ceo": {
                "global-overview": {
                    "title": "Global Overview",
                    "description": "Executive snapshot of hospital performance.",
                    "highlights": [
                        {"label": "Occupancy", "value": "78%"},
                        {"label": "Critical Cases", "value": 9},
                        {"label": "Active Alerts", "value": 6},
                    ],
                },
                "ai-insights": {
                    "title": "AI Insights",
                    "description": "AI-powered operational and clinical insights.",
                    "highlights": [
                        {"label": "Insights", "value": 14},
                        {"label": "High Risk", "value": 3},
                        {"label": "Recommendations", "value": 6},
                    ],
                },
                "department-analytics": {
                    "title": "Department Analytics",
                    "description": "Compare department performance and throughput.",
                    "highlights": [
                        {"label": "Departments", "value": 12},
                        {"label": "Avg LOS", "value": "4.2 days"},
                        {"label": "Utilization", "value": "81%"},
                    ],
                },
                "bed-management": {
                    "title": "Bed Management",
                    "description": "Track bed availability and occupancy.",
                    "highlights": [
                        {"label": "Available Beds", "value": 38},
                        {"label": "ICU Beds", "value": 12},
                        {"label": "Turnover", "value": "3.1 hrs"},
                    ],
                },
                "ambulance-coordination": {
                    "title": "Ambulance Coordination",
                    "description": "Coordinate inbound ambulances and ETAs.",
                    "highlights": [
                        {"label": "Active Units", "value": 5},
                        {"label": "Avg ETA", "value": "8 min"},
                        {"label": "Queued", "value": 2},
                    ],
                },
                "finance-overview": {
                    "title": "Finance Overview",
                    "description": "Monitor revenue and claims health.",
                    "highlights": [
                        {"label": "Monthly Revenue", "value": "$1.2M"},
                        {"label": "Claims Pending", "value": 18},
                        {"label": "Collections", "value": "92%"},
                    ],
                },
                "staff-management": {
                    "title": "Staff Management",
                    "description": "Coverage, staffing levels, and shift gaps.",
                    "highlights": [
                        {"label": "On Duty", "value": 214},
                        {"label": "Shift Gaps", "value": 3},
                        {"label": "Overtime Alerts", "value": 5},
                    ],
                },
                "reports": {
                    "title": "Reports",
                    "description": "Generate executive and operational reports.",
                    "highlights": [
                        {"label": "Reports", "value": 6},
                        {"label": "Pending Review", "value": 2},
                        {"label": "Compliance", "value": "100%"},
                    ],
                },
                "multi-hospital-network": {
                    "title": "Multi-Hospital Network",
                    "description": "Coordinate with partner hospitals and transfers.",
                    "highlights": [
                        {"label": "Partner Sites", "value": 4},
                        {"label": "Transfers", "value": 3},
                        {"label": "Capacity Alerts", "value": 1},
                    ],
                },
            },
            "emergency": {
                "live-emergency-feed": {
                    "title": "Live Emergency Feed",
                    "description": "Monitor incoming SOS alerts and triage.",
                    "highlights": [
                        {"label": "Active Alerts", "value": 6},
                        {"label": "Critical", "value": 2},
                        {"label": "Avg Response", "value": "7 min"},
                    ],
                },
                "ambulance-tracking": {
                    "title": "Ambulance Tracking",
                    "description": "Track inbound ambulances and locations.",
                    "highlights": [
                        {"label": "In Transit", "value": 3},
                        {"label": "Arriving", "value": 1},
                        {"label": "Dispatched", "value": 2},
                    ],
                },
                "patient-intake": {
                    "title": "Patient Intake",
                    "description": "Manage incoming patient registration.",
                    "highlights": [
                        {"label": "Waiting", "value": 8},
                        {"label": "Critical", "value": 2},
                        {"label": "Avg Wait", "value": "12 min"},
                    ],
                },
                "bed-allocation": {
                    "title": "Bed Allocation",
                    "description": "Allocate beds by severity and ward.",
                    "highlights": [
                        {"label": "ICU Beds", "value": 12},
                        {"label": "General Beds", "value": 26},
                        {"label": "Reserved", "value": 4},
                    ],
                },
                "ai-decision-panel": {
                    "title": "AI Decision Panel",
                    "description": "AI triage recommendations and insights.",
                    "highlights": [
                        {"label": "Recommendations", "value": 5},
                        {"label": "Escalations", "value": 2},
                        {"label": "Confidence", "value": "0.86"},
                    ],
                },
            },
            "finance": {
                "billing": {
                    "title": "Billing",
                    "description": "Invoice status and payment tracking.",
                    "highlights": [
                        {"label": "Invoices", "value": 42},
                        {"label": "Pending", "value": 8},
                        {"label": "Overdue", "value": 3},
                    ],
                },
                "revenue-analytics": {
                    "title": "Revenue Analytics",
                    "description": "Revenue trends and KPI analysis.",
                    "highlights": [
                        {"label": "Growth", "value": "+6%"},
                        {"label": "AR Days", "value": 34},
                        {"label": "Collections", "value": "92%"},
                    ],
                },
                "insurance": {
                    "title": "Insurance",
                    "description": "Claims approval and denial analysis.",
                    "highlights": [
                        {"label": "Claims Review", "value": 26},
                        {"label": "Approved", "value": 21},
                        {"label": "Denied", "value": 4},
                    ],
                },
                "cost-optimization": {
                    "title": "Cost Optimization",
                    "description": "Track cost savings and utilization gaps.",
                    "highlights": [
                        {"label": "Savings", "value": "$42K"},
                        {"label": "Alerts", "value": 3},
                        {"label": "Budget", "value": "81%"},
                    ],
                },
            },
            "opd": {
                "appointment-scheduling": {
                    "title": "Appointment Scheduling",
                    "description": "Manage OPD appointment slots.",
                    "highlights": [
                        {"label": "Appointments", "value": 86},
                        {"label": "No Shows", "value": 4},
                        {"label": "Avg Wait", "value": "18 min"},
                    ],
                },
                "doctor-management": {
                    "title": "Doctor Management",
                    "description": "Doctor availability and coverage.",
                    "highlights": [
                        {"label": "On Duty", "value": 24},
                        {"label": "Specialties", "value": 9},
                        {"label": "Coverage Gaps", "value": 1},
                    ],
                },
                "patient-queue": {
                    "title": "Patient Queue",
                    "description": "OPD queue visibility and routing.",
                    "highlights": [
                        {"label": "Waiting", "value": 18},
                        {"label": "Priority", "value": 3},
                        {"label": "Avg Wait", "value": "21 min"},
                    ],
                },
                "consultation-records": {
                    "title": "Consultation Records",
                    "description": "Review outpatient consultation logs.",
                    "highlights": [
                        {"label": "Consultations", "value": 64},
                        {"label": "Follow-ups", "value": 12},
                        {"label": "Pending Notes", "value": 5},
                    ],
                },
            },
            "icu": {
                "live-patient-monitoring": {
                    "title": "Live Patient Monitoring",
                    "description": "ICU vitals monitoring and staffing.",
                    "highlights": [
                        {"label": "ICU Beds", "value": 32},
                        {"label": "Ventilators", "value": 18},
                        {"label": "Staff", "value": 24},
                    ],
                },
                "critical-alerts": {
                    "title": "Critical Alerts",
                    "description": "ICU alerts and escalation tracking.",
                    "highlights": [
                        {"label": "Active Alerts", "value": 3},
                        {"label": "Escalated", "value": 1},
                        {"label": "Resolved", "value": 7},
                    ],
                },
                "ai-risk-prediction": {
                    "title": "AI Risk Prediction",
                    "description": "Predict ICU risk levels and deterioration.",
                    "highlights": [
                        {"label": "High Risk", "value": 4},
                        {"label": "Moderate", "value": 6},
                        {"label": "Stable", "value": 22},
                    ],
                },
                "vitals-dashboard": {
                    "title": "Vitals Dashboard",
                    "description": "ICU vital trends and stability scores.",
                    "highlights": [
                        {"label": "Stability", "value": "78%"},
                        {"label": "Critical Trend", "value": 2},
                        {"label": "Last Update", "value": "2 min ago"},
                    ],
                },
            },
            "radiology": {
                "scan-requests": {
                    "title": "Scan Requests",
                    "description": "Manage imaging requests and priorities.",
                    "highlights": [
                        {"label": "Pending", "value": 18},
                        {"label": "Urgent", "value": 4},
                        {"label": "Avg Turnaround", "value": "42 min"},
                    ],
                },
                "report-upload": {
                    "title": "Report Upload",
                    "description": "Upload imaging reports to the care team.",
                    "highlights": [
                        {"label": "Pending", "value": 6},
                        {"label": "Completed", "value": 22},
                        {"label": "Critical Reads", "value": 3},
                    ],
                },
                "ai-scan-insights": {
                    "title": "AI Scan Insights",
                    "description": "Future-ready AI imaging insights.",
                    "highlights": [
                        {"label": "AI Triage", "value": "Beta"},
                        {"label": "Insights", "value": 0},
                        {"label": "Readiness", "value": "Planned"},
                    ],
                },
            },
            "ot": {
                "surgery-scheduling": {
                    "title": "Surgery Scheduling",
                    "description": "Plan surgeries and OT readiness.",
                    "highlights": [
                        {"label": "Surgeries Today", "value": 14},
                        {"label": "Rooms Available", "value": 3},
                        {"label": "Avg Turnover", "value": "38 min"},
                    ],
                },
                "staff-allocation": {
                    "title": "Staff Allocation",
                    "description": "Assign surgical teams and OT staffing.",
                    "highlights": [
                        {"label": "Teams On Call", "value": 6},
                        {"label": "Coverage", "value": "96%"},
                        {"label": "Open Shifts", "value": 2},
                    ],
                },
                "equipment-tracking": {
                    "title": "Equipment Tracking",
                    "description": "Track OT equipment readiness and usage.",
                    "highlights": [
                        {"label": "Critical Kits", "value": 4},
                        {"label": "Sterilized", "value": 12},
                        {"label": "Maintenance", "value": 1},
                    ],
                },
            },
        }

    def list_modules(self, sub_role: str | None) -> dict:
        module_set = self._modules.get(sub_role or "", {})
        if not module_set:
            raise HTTPException(status_code=400, detail="Hospital subRole required")
        modules = [
            {"key": key, "title": value["title"], "description": value["description"]}
            for key, value in module_set.items()
        ]
        return {"subRole": sub_role, "modules": modules}

    def get_module(self, sub_role: str | None, module_key: str) -> dict:
        module_set = self._modules.get(sub_role or "", {})
        if not module_set:
            raise HTTPException(status_code=400, detail="Hospital subRole required")
        module = module_set.get(module_key)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"key": module_key, **module}
