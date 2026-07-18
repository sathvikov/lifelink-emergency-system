from __future__ import annotations

from datetime import datetime
import re


def _task_key(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "task"


def _card(
    title: str,
    summary: str,
    required: list[str],
    outputs: list[str],
    data_sources: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "summary": summary,
        "required_data": required,
        "outputs": outputs,
        "data_sources": data_sources or [],
        "confidence": 0.78,
        "status": "ready",
        "task_key": _task_key(title),
    }


PUBLIC_CATALOG = {
    "emergency": [
        _card(
            "Emergency Helper",
            "Turn your SOS message into clear next steps.",
            ["SOS message", "location", "vitals"],
            ["priority summary", "urgency level", "next steps"],
            ["alerts", "emergency_events"],
        ),
        _card(
            "Worsening Alert",
            "Estimate if the situation might get worse soon.",
            ["symptoms", "history", "response time"],
            ["risk level", "arrival time range"],
            ["alerts", "health_records"],
        ),
        _card(
            "Voice Summary",
            "Turn your voice message into a short summary.",
            ["voice message", "location"],
            ["summary", "handoff notes"],
            ["alerts"],
        ),
        _card(
            "Arrival Time Range",
            "Show a time range for when help will arrive.",
            ["route", "traffic", "weather"],
            ["arrival window", "time range"],
            ["analytics_events"],
        ),
    ],
    "health-dashboard": [
        _card(
            "Risk Timeline",
            "Show changes in risk over time and flag unusual days.",
            ["vitals history", "meds", "sleep activity"],
            ["trend line", "unusual days"],
            ["health_records", "predictions"],
        ),
        _card(
            "Preventive Reminders",
            "Create reminders based on your patterns.",
            ["age", "conditions", "care plan"],
            ["reminder list"],
            ["health_records"],
        ),
        _card(
            "Symptom Pattern Watch",
            "Spot repeated symptom patterns early.",
            ["symptom logs", "activity"],
            ["pattern labels", "early warnings"],
            ["analytics_events"],
        ),
        _card(
            "Lifestyle Change Alert",
            "Flag sudden changes in activity, sleep, or vitals.",
            ["wearable stream", "sleep activity"],
            ["alerts", "next steps"],
            ["health_records"],
        ),
    ],
    "health-risk": [
        _card(
            "Risk Breakdown",
            "Show what is driving the risk score and what to do next.",
            ["age", "bmi", "bp", "lifestyle"],
            ["risk drivers", "next steps"],
            ["predictions"],
        ),
        _card(
            "What-if Check",
            "See how small changes affect risk.",
            ["baseline vitals", "change ideas"],
            ["projected risk"],
            ["predictions"],
        ),
        _card(
            "Care Plan",
            "Create a simple plan with small steps.",
            ["risk profile", "goals"],
            ["care plan"],
            ["health_records"],
        ),
        _card(
            "Risk History",
            "Store and compare past risk scores.",
            ["risk profile", "dates"],
            ["risk history"],
            ["predictions"],
        ),
    ],
    "medical-records": [
        _card(
            "History Summary",
            "Summarize your history across records.",
            ["health_records"],
            ["history summary"],
            ["health_records"],
        ),
        _card(
            "Condition Trend Alerts",
            "Detect worsening patterns across records.",
            ["labs", "diagnoses"],
            ["trend alerts"],
            ["health_records"],
        ),
        _card(
            "Medication Interaction Check",
            "Flag possible medication conflicts.",
            ["medication list"],
            ["interaction alerts"],
            ["health_records"],
        ),
        _card(
            "Multi-record Summary",
            "Summarize trends across record types.",
            ["records", "labs", "diagnoses"],
            ["summary"],
            ["health_records"],
        ),
        _card(
            "Smart Record Search",
            "Search records by meaning.",
            ["search query"],
            ["matches"],
            ["health_records", "knowledge_chunks"],
        ),
    ],
    "donor-matching": [
        _card(
            "Best Match List",
            "Rank donors by match and travel time.",
            ["donor profiles", "requester profile"],
            ["ranked donors"],
            ["donations", "users"],
        ),
        _card(
            "Supply Demand Forecast",
            "Forecast donation gaps for the next 30 days.",
            ["donation history", "regional demand"],
            ["forecast"],
            ["donations"],
        ),
        _card(
            "Urgency Matching",
            "Prioritize donors based on urgency and location.",
            ["urgency", "distance"],
            ["priority list"],
            ["resource_requests"],
        ),
    ],
    "nearby-hospitals": [
        _card(
            "Capacity Preview",
            "Estimate bed availability and wait time.",
            ["bed occupancy", "admissions"],
            ["capacity score", "wait time"],
            ["resources", "hospital_departments"],
        ),
        _card(
            "Route Safety",
            "Score routes based on traffic and weather.",
            ["route", "traffic", "weather"],
            ["safety score"],
            ["analytics_events"],
        ),
        _card(
            "Specialty Match",
            "Match your needs to hospital specialties.",
            ["condition", "hospital specialties"],
            ["match score"],
            ["hospitals"],
        ),
    ],
    "family-monitoring": [
        _card(
            "Wellness Trend Watch",
            "Detect changes in vitals or check-in patterns.",
            ["member check-ins", "vitals"],
            ["trend alerts"],
            ["family_members"],
        ),
        _card(
            "Reminder Nudges",
            "Send gentle reminders for missed check-ins.",
            ["care plan", "missed events"],
            ["reminders"],
            ["family_members"],
        ),
        _card(
            "Caregiver Plan",
            "Recommend caregiver rotations and check-in timing.",
            ["family schedule"],
            ["plan"],
            ["family_members"],
        ),
        _card(
            "Location Alerts",
            "Notify when someone leaves expected areas.",
            ["member location", "safe area"],
            ["location alerts"],
            ["family_members"],
        ),
    ],
    "lifelink-ai-search": [
        _card(
            "Answers with Sources",
            "Show answers and where they came from.",
            ["search index"],
            ["answer", "sources"],
            ["knowledge_chunks"],
        ),
        _card(
            "Search Helper",
            "Suggest extra words to improve search.",
            ["search query"],
            ["expanded query"],
            ["knowledge_chunks"],
        ),
        _card(
            "Personalized Search",
            "Tailor search to your profile and needs.",
            ["search query", "profile"],
            ["personalized query"],
            ["knowledge_chunks", "users"],
        ),
        _card(
            "Safety Notes",
            "Add safety notes when risk is higher.",
            ["answer", "risk context"],
            ["safety notes"],
            ["health_records"],
        ),
    ],
}

HOSPITAL_CATALOG = {
    "ceo": {
        "global-overview": [
            _card(
                "Hospital Digital Twin",
                "Simulate capacity and patient flow under stress.",
                ["beds", "staff", "admissions"],
                ["simulation_summary"],
                ["beds", "hospital_staff"],
            ),
            _card(
                "Cross-Facility Benchmarking",
                "Compare throughput and outcomes across peer hospitals.",
                ["network_metrics"],
                ["benchmark_scores"],
                ["hospitals"],
            ),
        ],
        "ai-insights": [
            _card(
                "KPI Anomaly Radar",
                "Detect abnormal changes in revenue, beds, and ER load.",
                ["metrics"],
                ["anomaly_flags"],
                ["analytics_events"],
            ),
            _card(
                "Resource Cost Optimizer",
                "Recommend cost-saving levers without affecting care.",
                ["expenses", "usage"],
                ["savings_plan"],
                ["finance_expenses"],
            ),
        ],
        "department-analytics": [
            _card(
                "Throughput Forecast",
                "Forecast department throughput for next 7 days.",
                ["department_logs"],
                ["throughput_forecast"],
                ["department_logs"],
            ),
            _card(
                "Bottleneck Finder",
                "Identify departments causing downstream delays.",
                ["department_logs"],
                ["bottlenecks"],
                ["department_logs"],
            )
        ],
        "bed-management": [
            _card(
                "Auto Allocation Suggestions",
                "Recommend bed assignment strategy per unit.",
                ["bed_inventory", "incoming_cases"],
                ["allocation_plan"],
                ["bed_allocations"],
            ),
            _card(
                "Discharge Timing Optimizer",
                "Predict optimal discharge windows to free beds.",
                ["patient_progress"],
                ["discharge_windows"],
                ["patients"],
            )
        ],
        "resource-management": [
            _card(
                "Supply Chain Risk",
                "Predict risk of stockout and reorder windows.",
                ["inventory", "vendor_lead_time"],
                ["reorder_plan"],
                ["equipment_inventory", "resources"],
            ),
            _card(
                "Utilization Forecast",
                "Forecast resource usage for the next 14 days.",
                ["usage_logs"],
                ["utilization_forecast"],
                ["equipment_inventory"],
            )
        ],
        "ambulance-coordination": [
            _card(
                "Load-aware Dispatch",
                "Balance incoming ambulances based on hospital load.",
                ["ambulance_status", "hospital_load"],
                ["dispatch_plan"],
                ["ambulances", "resources"],
            ),
            _card(
                "Handoff Summary Builder",
                "Generate a concise handoff summary for incoming crews.",
                ["case_notes"],
                ["handoff_summary"],
                ["alerts"],
            )
        ],
        "finance-overview": [
            _card(
                "Margin Forecast",
                "Predict margin trends and leakage risks.",
                ["billing", "claims", "expenses"],
                ["margin_forecast"],
                ["billing_invoices", "finance_expenses"],
            ),
            _card(
                "Leakage Detector",
                "Identify revenue leakage from claim denials.",
                ["claims"],
                ["leakage_flags"],
                ["insurance_claims"],
            )
        ],
        "staff-management": [
            _card(
                "Staffing Demand Forecast",
                "Recommend staffing levels by shift.",
                ["roster", "patient_load"],
                ["staffing_plan"],
                ["hospital_staff"],
            ),
            _card(
                "Skill Mix Optimizer",
                "Balance skill coverage based on case mix.",
                ["skills", "case_mix"],
                ["skill_plan"],
                ["hospital_staff"],
            )
        ],
        "reports": [
            _card(
                "Auto Summary Builder",
                "Summarize reports with risks and compliance flags.",
                ["reports"],
                ["summary"],
                ["government_reports"],
            ),
            _card(
                "Compliance Highlight",
                "Highlight compliance changes since last report.",
                ["compliance"],
                ["compliance_summary"],
                ["government_compliance"],
            )
        ],
        "multi-hospital-network": [
            _card(
                "Transfer Recommender",
                "Suggest transfers based on capacity and specialties.",
                ["network_capacity"],
                ["transfer_recommendations"],
                ["hospitalmessages", "hospitals"],
            ),
            _card(
                "Mutual Aid Score",
                "Score partner hospitals for mutual aid readiness.",
                ["partner_metrics"],
                ["aid_scores"],
                ["hospitals"],
            )
        ],
    },
    "emergency": {
        "live-emergency-feed": [
            _card("Surge Predictor", "Predict incoming surge over next 2 hours.", ["alerts"], ["surge_risk"], ["alerts"]),
            _card("Escalation Heatmap", "Identify top escalation sources.", ["alerts"], ["heatmap"], ["alerts"]),
            _card("Multimodal Triage Assistant", "Fuse vitals, notes, and imaging cues.", ["vitals", "notes", "imaging_meta"], ["triage_recommendations"], ["icu_patients", "radiology_reports"]),
        ],
        "patient-intake": [
            _card("Triage Summary", "Auto summarize intake and risk band.", ["intake"], ["summary", "risk_band"], ["patients"]),
            _card("Critical Risk Banding", "Flag high-risk intakes for review.", ["vitals"], ["risk_band"], ["patients"]),
        ],
        "bed-allocation": [
            _card("Critical Path Orchestration", "Recommend routing and bed usage.", ["beds", "triage"], ["path_plan"], ["bed_allocations"]),
            _card("Overflow Routing", "Recommend overflow destinations.", ["beds", "alerts"], ["overflow_plan"], ["bed_allocations", "alerts"]),
        ],
        "ai-decision-panel": [
            _card("Realtime Triage Assistant", "Assist decisions with updated signals.", ["events"], ["recommendation"], ["analytics_events"]),
            _card("Handoff Brief", "Auto-generate handoff brief.", ["case_notes"], ["brief"], ["alerts"]),
            _card("Ambulance Handoff Summary", "Summarize ambulance handoff context.", ["ambulance_notes"], ["handoff_summary"], ["ambulance_assignments"]),
        ],
        "ambulance-tracking": [
            _card("Load-aware Assignment", "Route ambulances to balanced facilities.", ["ambulance_status", "hospital_load"], ["assignment_plan"], ["ambulances", "resources"]),
            _card("Reroute-on-Incident Alerts", "Reroute on new incident signals.", ["alerts", "routes"], ["reroute_plan"], ["alerts"]),
        ],
    },
    "finance": {
        "billing": [
            _card("Claims Anomaly Detection", "Flag invoice anomalies.", ["invoices"], ["anomaly_flags"], ["billing_invoices"]),
            _card("Payment Delay Risk", "Predict late payment risk.", ["invoices"], ["delay_risk"], ["billing_invoices"]),
        ],
        "revenue-analytics": [
            _card("Payer Mix Forecast", "Forecast payer distribution and revenue.", ["claims"], ["payer_forecast"], ["insurance_claims"]),
            _card("Service Line Profitability", "Rank profitable service lines.", ["expenses"], ["profit_rank"], ["finance_expenses"]),
            _card("Revenue Leakage Model", "Identify leakage from denials and delays.", ["claims", "payments"], ["leakage_risk"], ["insurance_claims"]),
        ],
        "insurance": [
            _card("Rejection Predictor", "Predict claim rejection risk.", ["claims"], ["risk_score"], ["insurance_claims"]),
            _card("Claim Recovery Plan", "Recommend recovery steps.", ["claims"], ["recovery_plan"], ["insurance_claims"]),
        ],
        "cost-optimization": [
            _card("Resource Cost Optimizer", "Optimize staffing and supply costs.", ["expenses", "usage"], ["savings_plan"], ["finance_expenses"]),
            _card("Contract Leak Detector", "Detect contract overages and waste.", ["vendor_contracts"], ["leakage_flags"], ["finance_expenses"]),
        ],
    },
    "opd": {
        "appointment-scheduling": [
            _card("Demand Forecast", "Forecast OPD load and no-show risk.", ["appointments"], ["forecast"], ["opd_appointments"]),
            _card("No-show Predictor", "Flag high no-show risk appointments.", ["appointments"], ["no_show_risk"], ["opd_appointments"]),
        ],
        "doctor-management": [
            _card("Staffing Optimizer", "Recommend doctors per slot.", ["schedule"], ["optimizer_plan"], ["opd_doctors"]),
            _card("Skill Coverage Map", "Suggest specialty coverage by hour.", ["schedule"], ["coverage_map"], ["opd_doctors"]),
        ],
        "patient-queue": [
            _card("Wait-time Predictor", "Predict queue wait time.", ["queue"], ["wait_time"], ["opd_queue"]),
            _card("Queue Priority Flags", "Highlight urgent cases.", ["queue"], ["priority_flags"], ["opd_queue"]),
        ],
        "consultation-records": [
            _card("AI Scribe Summary", "Summarize consult notes.", ["notes"], ["summary"], ["opd_consultations"]),
            _card("Follow-up Planner", "Suggest follow-up schedule.", ["notes"], ["follow_up_plan"], ["opd_consultations"]),
        ],
    },
    "icu": {
        "live-patient-monitoring": [
            _card("Deterioration Model", "Predict early deterioration risk.", ["vitals"], ["risk_score"], ["icu_patients"]),
            _card("Stability Index", "Score patient stability over last 12 hours.", ["vitals"], ["stability_index"], ["icu_patients"]),
        ],
        "critical-alerts": [
            _card("Sepsis Risk Scoring", "Identify possible sepsis.", ["labs", "vitals"], ["sepsis_score"], ["icu_alerts"]),
            _card("Alert Fatigue Filter", "Reduce duplicate alerts.", ["alerts"], ["filtered_alerts"], ["icu_alerts"]),
        ],
        "ai-risk-prediction": [
            _card("Vent Weaning Guidance", "Recommend weaning readiness.", ["vent_data"], ["guidance"], ["icu_patients"]),
            _card("ICU Discharge Readiness", "Score readiness for step-down.", ["vitals"], ["readiness_score"], ["icu_patients"]),
        ],
        "vitals-dashboard": [
            _card("Trend Anomaly Alerts", "Detect unusual vitals trends.", ["vitals"], ["anomaly_flags"], ["icu_patients"]),
            _card("Vitals Forecast", "Predict next-hour vitals range.", ["vitals"], ["forecast_band"], ["icu_patients"]),
        ],
    },
    "radiology": {
        "scan-requests": [
            _card("Priority Queue", "Auto-rank scans by urgency.", ["requests"], ["queue_rank"], ["radiology_requests"]),
            _card("Turnaround Predictor", "Estimate report turnaround time.", ["requests"], ["eta"], ["radiology_requests"]),
        ],
        "report-upload": [
            _card("Draft Report Assist", "Generate initial report draft.", ["metadata"], ["draft"], ["radiology_reports"]),
            _card("Finding Consistency", "Check report consistency vs notes.", ["report", "notes"], ["consistency_flags"], ["radiology_reports"]),
        ],
        "ai-scan-insights": [
            _card("Modality QA", "Quality checks for imaging.", ["imaging_meta"], ["qa_flags"], ["radiology_reports"]),
            _card("Image Completeness", "Flag missing or partial series.", ["imaging_meta"], ["completeness_flags"], ["radiology_reports"]),
        ],
    },
    "ot": {
        "surgery-scheduling": [
            _card("Duration Predictor", "Estimate surgery duration.", ["case_history"], ["duration_estimate"], ["ot_surgeries"]),
            _card("Turnover Optimizer", "Optimize turnover gaps.", ["schedule"], ["turnover_plan"], ["ot_surgeries"]),
            _card("Schedule Optimizer", "Rebalance OT blocks for throughput.", ["schedule", "staff"], ["optimized_schedule"], ["ot_surgeries"]),
        ],
        "staff-allocation": [
            _card("Readiness Optimizer", "Optimize staff allocation.", ["roster"], ["allocation_plan"], ["ot_allocations"]),
            _card("Skill Coverage", "Ensure critical skills per case.", ["roster"], ["coverage_flags"], ["ot_allocations"]),
        ],
        "equipment-tracking": [
            _card("Utilization Forecast", "Predict equipment utilization.", ["usage"], ["util_forecast"], ["equipment_inventory"]),
            _card("Sterilization Scheduler", "Suggest sterilization windows.", ["usage"], ["schedule"], ["equipment_inventory"]),
            _card("Equipment Readiness", "Flag readiness risks before cases.", ["maintenance_logs"], ["readiness_flags"], ["equipment_inventory"]),
        ],
    },
}

AMBULANCE_CATALOG = {
    "assignments": [
        _card("Predictive Prioritization", "Rank assignments by risk and distance.", ["assignments"], ["priority_rank"], ["ambulance_assignments"]),
        _card("Crew Load Balancer", "Balance assignments across crews.", ["assignments"], ["balance_plan"], ["ambulance_assignments"]),
        _card("Multi-Ambulance Optimization", "Optimize routing across multiple units.", ["fleet_status"], ["dispatch_plan"], ["ambulances"]),
    ],
    "live-tracking": [
        _card("Route Risk Score", "Score route safety in real time.", ["route", "traffic", "weather"], ["risk_score"], ["analytics_events"]),
        _card("Incident Reroute", "Suggest reroute on new incidents.", ["alerts"], ["reroute_plan"], ["alerts"]),
    ],
    "patient-info": [
        _card("Pre-arrival Summary", "Summarize patient state for handoff.", ["vitals"], ["summary"], ["ambulance_assignments"]),
        _card("Critical Risk Flags", "Highlight red flags for handoff.", ["vitals"], ["risk_flags"], ["ambulance_assignments"]),
        _card("Voice-to-Case Log", "Auto-capture spoken case notes.", ["voice_transcript"], ["case_log"], ["ambulance_assignments"]),
        _card("Smart Vitals Triage", "Suggest triage band from vitals.", ["vitals"], ["triage_band"], ["ambulance_assignments"]),
    ],
    "navigation": [
        _card("Multi-route Ranking", "Recommend best routes by ETA and load.", ["routes"], ["ranked_routes"], ["analytics_events"]),
        _card("Load-aware ETA", "Adjust ETA by hospital load.", ["routes", "hospital_load"], ["eta_adjusted"], ["resources"]),
        _card("Hospital Load-aware Assignment", "Assign by live hospital capacity.", ["hospital_load", "fleet_status"], ["assignment_plan"], ["resources"]),
    ],
    "emergency-status": [
        _card("Surge Warning", "Predict emerging surge zones.", ["alerts"], ["surge_zones"], ["alerts"]),
        _card("Response Heatmap", "Highlight coverage gaps.", ["ambulance_tracks"], ["gap_map"], ["ambulances"]),
    ],
    "history": [
        _card("Outcome Prediction", "Predict outcomes based on history.", ["missions"], ["outcome_risk"], ["ambulance_assignments"]),
        _card("Protocol Review", "Suggest protocol improvements.", ["mission_notes"], ["protocol_changes"], ["ambulance_assignments"]),
        _card("Predictive Maintenance", "Forecast maintenance needs per unit.", ["maintenance_logs"], ["maintenance_forecast"], ["ambulances"]),
        _card("Fuel/Route Efficiency", "Score efficiency across routes and crews.", ["route_history"], ["efficiency_score"], ["ambulance_assignments"]),
    ],
}

GOVERNMENT_CATALOG = {
    "national_admin": {
        "country-dashboard": [
            _card("National Digital Twin", "Simulate national capacity stress.", ["national_metrics"], ["sim_output"], ["hospitals"]),
            _card("Cross-Region Benchmark", "Compare regions on response KPIs.", ["regional_metrics"], ["benchmark"], ["alerts"]),
        ],
        "emergency-heatmap": [
            _card("Hotspot Evolution", "Predict hotspot movement.", ["heatmap"], ["trend_map"], ["alerts"]),
            _card("Severity Drift", "Detect severity drift across regions.", ["alerts"], ["drift_score"], ["alerts"]),
            _card("Outbreak Early Warning", "Detect early outbreak signals.", ["alerts", "symptom_trends"], ["outbreak_flags"], ["alerts"]),
        ],
        "resource-allocation": [
            _card("Supply Chain Risk", "Forecast supply gaps.", ["regional_supply"], ["risk_forecast"], ["resources"]),
            _card("Surge Allocation Plan", "Allocate surge supplies by region.", ["surge"], ["allocation_plan"], ["resources"]),
            _card("Inter-state Resource Simulation", "Simulate cross-region resource shifts.", ["resource_inventory"], ["simulation_output"], ["resources"]),
        ],
        "policy-insights": [
            _card("Policy Impact Model", "Simulate policy outcomes.", ["policy_inputs"], ["impact_score"], ["government_reports"]),
            _card("Compliance Predictor", "Forecast compliance shifts.", ["compliance"], ["compliance_risk"], ["government_compliance"]),
        ],
    },
    "state_admin": {
        "state-dashboard": [
            _card("State Capacity Forecast", "Predict statewide bed demand.", ["state_metrics"], ["capacity_forecast"], ["hospitals"]),
            _card("Resource Gap Index", "Identify resource gaps by district.", ["resources"], ["gap_index"], ["resources"]),
            _card("Hotspot Evolution", "Forecast district-level hotspot shifts.", ["heatmap"], ["trend_map"], ["alerts"]),
        ],
        "hospital-monitoring": [
            _card("Compliance Risk Scoring", "Score hospitals by compliance risk.", ["audit_logs"], ["risk_scores"], ["audit_logs"]),
            _card("Performance Outliers", "Detect hospital performance outliers.", ["metrics"], ["outlier_flags"], ["analytics_events"]),
        ],
        "reports": [
            _card("Auto Summary", "Summarize report themes.", ["reports"], ["summary"], ["government_reports"]),
            _card("Risk Highlights", "Highlight emerging risks.", ["reports"], ["risk_highlights"], ["government_reports"]),
        ],
    },
    "district_admin": {
        "district-emergencies": [
            _card("Incident Clustering", "Cluster incidents by root cause.", ["alerts"], ["clusters"], ["alerts"]),
            _card("Peak Window Predictor", "Predict peak incident windows.", ["alerts"], ["peak_windows"], ["alerts"]),
        ],
        "ambulance-tracking": [
            _card("Coverage Gaps", "Identify coverage gaps in real time.", ["ambulance_tracks"], ["gap_zones"], ["ambulances"]),
            _card("ETA Reliability", "Score ETA reliability by zone.", ["routes"], ["eta_reliability"], ["analytics_events"]),
        ],
    },
    "supervisory_authority": {
        "hospital-audits": [
            _card("Audit Anomaly Detection", "Detect irregular audits.", ["audits"], ["anomaly_flags"], ["audit_logs"]),
            _card("License Risk Flags", "Flag license risk by facility.", ["audits"], ["risk_flags"], ["audit_logs"]),
        ],
        "compliance-monitoring": [
            _card("Safety Compliance Score", "Score compliance trends.", ["compliance"], ["compliance_score"], ["government_compliance"]),
            _card("Penalty Predictor", "Forecast potential penalties.", ["compliance"], ["penalty_risk"], ["government_compliance"]),
        ],
    },
}


def build_insights(role: str, module_key: str, sub_role: str | None = None) -> dict:
    timestamp = datetime.utcnow().isoformat()
    role = (role or "public").lower()
    module_key = (module_key or "overview").lower()
    sub_role = (sub_role or "").lower() or None

    if role == "public":
        cards = PUBLIC_CATALOG.get(module_key, [])
    elif role == "hospital":
        cards = HOSPITAL_CATALOG.get(sub_role or "ceo", {}).get(module_key, [])
        if not cards:
            for catalog in HOSPITAL_CATALOG.values():
                if module_key in catalog:
                    cards = catalog[module_key]
                    break
        if not cards:
            cards = HOSPITAL_CATALOG.get("ceo", {}).get(module_key, [])
    elif role == "ambulance":
        cards = AMBULANCE_CATALOG.get(module_key, [])
    elif role == "government":
        cards = GOVERNMENT_CATALOG.get(sub_role or "national_admin", {}).get(module_key, [])
        if not cards:
            for catalog in GOVERNMENT_CATALOG.values():
                if module_key in catalog:
                    cards = catalog[module_key]
                    break
        if not cards:
            cards = GOVERNMENT_CATALOG.get("national_admin", {}).get(module_key, [])
    else:
        cards = []

    return {
        "role": role,
        "sub_role": sub_role,
        "module_key": module_key,
        "timestamp": timestamp,
        "cards": cards,
    }
