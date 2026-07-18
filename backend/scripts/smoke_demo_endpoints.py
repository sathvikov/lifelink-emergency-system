import json
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BASE_URL = os.getenv("LIFELINK_API_URL", "http://localhost:3010").rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("LIFELINK_SMOKE_TIMEOUT", "25"))
DEMO_PASSWORD = "Demo@2026!"


def _auth_header(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


@dataclass
class TestResult:
    name: str
    method: str
    path: str
    status: int | None
    ok: bool
    detail: str | None = None


class SmokeTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)
        self.results: list[TestResult] = []

    def close(self) -> None:
        self.client.close()

    def _record(self, name: str, method: str, path: str, status: int | None, ok: bool, detail: str | None = None) -> None:
        self.results.append(TestResult(name=name, method=method, path=path, status=status, ok=ok, detail=detail))

    def request(
        self,
        name: str,
        method: str,
        path: str,
        token: str | None = None,
        json_body: dict | list | None = None,
        params: dict[str, Any] | None = None,
        expected: set[int] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        expected = expected or {200}
        try:
            response = self.client.request(
                method,
                path,
                headers=_auth_header(token),
                json=json_body,
                params=params,
                timeout=timeout_seconds or TIMEOUT_SECONDS,
            )
        except Exception as exc:
            self._record(name, method, path, None, False, f"request_failed: {exc}")
            return None

        ok = response.status_code in expected
        detail = None
        data = None
        try:
            data = response.json()
        except Exception:
            data = None

        if not ok:
            if isinstance(data, dict):
                detail = json.dumps(data)
            else:
                detail = response.text[:500]
        self._record(name, method, path, response.status_code, ok, detail)
        return data

    def login(self, role: str, email: str | None = None, hospital_id: str | None = None) -> tuple[str, dict]:
        payload: dict[str, Any] = {
            "password": DEMO_PASSWORD,
            "role": role,
        }
        if role == "hospital":
            payload["hospitalId"] = hospital_id
        else:
            payload["email"] = email

        data = self.request(
            name=f"login:{role}",
            method="POST",
            path="/v2/auth/login",
            json_body=payload,
            expected={200},
        )
        if not data or "token" not in data:
            raise RuntimeError(f"Login failed for role {role}")
        return data["token"], data.get("user", {})

    def select_role(self, token: str, sub_role: str) -> tuple[str, dict]:
        data = self.request(
            name=f"select-role:{sub_role}",
            method="POST",
            path="/v2/auth/select-role",
            token=token,
            json_body={"subRole": sub_role},
            expected={200},
        )
        if not data or "token" not in data:
            raise RuntimeError(f"Select role failed for {sub_role}")
        return data["token"], data.get("user", {})


def _print_summary(results: list[TestResult]) -> None:
    total = len(results)
    passed = len([r for r in results if r.ok])
    failed = [r for r in results if not r.ok]
    print(f"\nSmoke results: {passed}/{total} passed")
    if failed:
        print("\nFailures:")
        for item in failed:
            status = item.status if item.status is not None else "ERR"
            print(f"- {item.name} [{status}] {item.method} {item.path}")
            if item.detail:
                print(f"  {item.detail}")


def _write_reports(results: list[TestResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = f"smoke_demo_report_{timestamp}"
    json_path = output_dir / f"{base}.json"
    md_path = output_dir / f"{base}.md"

    total = len(results)
    passed = len([r for r in results if r.ok])
    failed = [r for r in results if not r.ok]

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "base_url": BASE_URL,
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "results": [
            {
                "name": r.name,
                "method": r.method,
                "path": r.path,
                "status": r.status,
                "ok": r.ok,
                "detail": r.detail,
            }
            for r in results
        ],
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Smoke Test Report",
        "",
        f"Generated: {payload['generated_at']}",
        f"Base URL: {payload['base_url']}",
        f"Summary: {payload['passed']}/{payload['total']} passed",
        "",
        "## Failures",
    ]

    if not failed:
        lines.append("None")
    else:
        lines.append("| Name | Method | Path | Status | Detail |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in failed:
            status = item.status if item.status is not None else "ERR"
            detail = (item.detail or "").replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {item.name} | {item.method} | {item.path} | {status} | {detail} |")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    tester = SmokeTester(BASE_URL)
    try:
        # Public portal
        public_token, public_user = tester.login("public", email="public.001@lifelink.demo")
        public_id = public_user.get("id") or public_user.get("_id")

        tester.request(
            "public_dashboard",
            "GET",
            f"/api/dashboard/public/{public_id}/full",
            token=public_token,
        )
        tester.request("public_notifications", "GET", f"/api/notifications/{public_id}", token=public_token)
        tester.request("public_health_records", "GET", f"/api/health/records/{public_id}", token=public_token)
        tester.request("public_health_risk_history", "GET", f"/api/health/risk/history/{public_id}", token=public_token)
        tester.request("public_donors", "GET", "/api/donors", token=public_token)
        tester.request("public_donors_forecast", "GET", "/api/donors/forecast", token=public_token)
        tester.request("public_family_members", "GET", f"/api/family/members/{public_id}", token=public_token)
        tester.request("public_family_insights", "GET", f"/api/family/insights/{public_id}", token=public_token)
        tester.request(
            "public_agents_ask",
            "POST",
            "/v2/agents/ask",
            token=public_token,
            json_body={
                "query": "Find a nearby hospital for a cardiac emergency",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
            timeout_seconds=120,
        )
        tester.request(
            "public_health_risk_v2",
            "POST",
            "/v2/ml/health-risk",
            token=public_token,
            json_body={
                "user_id": public_id,
                "age": 55,
                "bmi": 28.2,
                "blood_pressure": 132,
                "heart_rate": 82,
            },
        )
        tester.request(
            "public_health_risk_v1",
            "POST",
            "/api/predict_health_risk",
            token=public_token,
            json_body={"age": 55, "bmi": 28.2, "blood_pressure": 132, "heart_rate": 82},
        )
        tester.request(
            "public_user_forecast",
            "POST",
            "/api/predict_user_forecast",
            token=public_token,
            json_body={"user_id": public_id, "age": 55, "activity_level": "moderate"},
        )
        tester.request(
            "public_user_cluster",
            "POST",
            "/api/predict_user_cluster",
            token=public_token,
            json_body={"user_id": public_id},
        )
        tester.request(
            "public_check_compatibility",
            "POST",
            "/api/check_compatibility",
            token=public_token,
            json_body={
                "requester_id": public_id,
                "donor_id": public_id,
                "organ_type": "Blood",
            },
        )
        tester.request(
            "public_analyze_report",
            "POST",
            "/api/analyze_report",
            token=public_token,
            json_body={"report_text": "Patient has asthma and hypertension.", "user_id": public_id},
        )

        sos = tester.request(
            "public_sos_create",
            "POST",
            "/v2/public/sos",
            token=public_token,
            json_body={
                "userId": public_id,
                "message": "Severe chest pain and dizziness",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
            timeout_seconds=120,
        )
        sos_id = (sos or {}).get("id") or (sos or {}).get("_id") or (sos or {}).get("sos_id")
        if sos_id:
            tester.request("public_sos_get", "GET", f"/v2/public/sos/{sos_id}", token=public_token)

        tester.request(
            "public_donor_match",
            "POST",
            "/v2/public/donors/match",
            token=public_token,
            json_body={"blood_group": "O+", "urgency": "high", "latitude": 12.9716, "longitude": 77.5946},
        )

        tester.request(
            "public_hospital_nearby",
            "GET",
            "/v2/hospital/nearby",
            token=public_token,
            params={"lat": 12.9716, "lng": 77.5946, "limit": 5, "radius_km": 50, "include_eta": "true"},
        )

        tester.request(
            "public_resource_request",
            "POST",
            "/api/requests",
            token=public_token,
            json_body={
                "requester_id": public_id,
                "request_type": "supplies",
                "details": "Need additional PPE kits",
                "urgency": "high",
            },
            expected={201},
        )

        # Government portal
        gov_token, gov_user = tester.login("government", email="government.001@lifelink.demo")
        gov_token, gov_user = tester.select_role(gov_token, "national_admin")

        tester.request("gov_command_seed", "POST", "/v2/government/command/seed", token=gov_token, json_body={})
        tester.request("gov_command_overview", "GET", "/v2/government/command/overview", token=gov_token)
        tester.request("gov_decision_engine", "POST", "/v2/government/decision/engine", token=gov_token)
        tester.request("gov_monitoring_summary", "GET", "/v2/government/monitoring/summary", token=gov_token)
        tester.request("gov_monitoring_feed", "GET", "/v2/government/monitoring/feed", token=gov_token)
        tester.request("gov_resources_hospitals", "GET", "/v2/government/resources/hospitals", token=gov_token)
        tester.request("gov_resources_ambulances", "GET", "/v2/government/resources/ambulances", token=gov_token)
        tester.request("gov_predictions_anomaly", "GET", "/v2/government/predictions/anomaly", token=gov_token)
        tester.request(
            "gov_eva_ask",
            "POST",
            "/v2/government/ai/ask",
            token=gov_token,
            json_body={"query": "Show current hotspots and resource risks", "execute": False},
        )
        tester.request(
            "gov_policy_list",
            "GET",
            "/v2/government/policy/actions",
            token=gov_token,
        )
        tester.request(
            "gov_policy_create",
            "POST",
            "/v2/government/policy/actions",
            token=gov_token,
            json_body={"title": "Surge preparedness", "action": "Activate overflow beds", "status": "Draft"},
        )
        tester.request("gov_disaster_detect", "POST", "/v2/government/disaster/detect", token=gov_token)
        tester.request(
            "gov_disaster_trigger",
            "POST",
            "/v2/government/disaster/trigger",
            token=gov_token,
            json_body={"type": "manual", "severity": "High", "zone": "Zone A", "lat": 12.97, "lng": 77.59},
        )
        tester.request(
            "gov_disaster_broadcast",
            "POST",
            "/v2/government/disaster/broadcast",
            token=gov_token,
            json_body={"message": "Stay alert", "zone": "Zone A"},
        )
        tester.request("gov_disaster_recent", "GET", "/v2/government/disaster/recent", token=gov_token)
        sim = tester.request(
            "gov_simulation_start",
            "POST",
            "/v2/government/simulation/start",
            token=gov_token,
            json_body={"intensity": "medium"},
        )
        sim_id = (sim or {}).get("session_id")
        if sim_id:
            tester.request(
                "gov_simulation_multi_phase",
                "POST",
                "/v2/government/simulation/multi-phase",
                token=gov_token,
                json_body={
                    "session_id": sim_id,
                    "phases": [
                        {"name": "Phase 1", "intensity": "low", "count": 10, "duration": 15},
                        {"name": "Phase 2", "intensity": "high", "count": 15, "duration": 20},
                    ],
                },
            )
            tester.request(
                "gov_simulation_stop",
                "POST",
                f"/v2/government/simulation/stop/{sim_id}",
                token=gov_token,
            )
            tester.request(
                "gov_simulation_after_action",
                "POST",
                f"/v2/government/simulation/after-action/{sim_id}",
                token=gov_token,
            )

        # Government legacy ops (used in UI)
        tester.request("gov_legacy_reports", "GET", "/api/government-ops/reports", token=gov_token)
        tester.request("gov_legacy_compliance", "GET", "/api/government-ops/compliance", token=gov_token)
        tester.request("gov_legacy_hospitals", "GET", "/api/government-ops/hospitals", token=gov_token)
        tester.request("gov_legacy_emergencies", "GET", "/api/government-ops/emergencies", token=gov_token)

        # Hospital portal
        hospital_token, hospital_user = tester.login("hospital", hospital_id="HOSP-1001")
        hospital_token, hospital_user = tester.select_role(hospital_token, "finance")
        hospital_id = hospital_user.get("id") or hospital_user.get("_id")

        tester.request("hospital_profile", "GET", f"/api/hospital-communication/my-hospital/{hospital_id}", token=hospital_token)
        tester.request("hospital_resources", "GET", f"/api/hospital-ops/ceo/resources", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_bed_forecast", "GET", f"/api/hospital-ops/ceo/beds/forecast", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_department_performance", "GET", f"/api/hospital-ops/ceo/department-performance", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_emergency_feed", "GET", f"/api/hospital-ops/emergency/feed", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_staff", "GET", f"/api/hospital-ops/staff", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_staff_skills", "GET", f"/api/hospital-ops/staff/skills/summary", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_staff_optimizer", "GET", f"/api/hospital-ops/staff/optimizer", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_reports", "GET", f"/api/hospital-ops/reports", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_reports_ingested", "GET", f"/api/hospital-ops/reports/ingested", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_invoices", "GET", f"/api/hospital-ops/finance/invoices", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_revenue", "GET", f"/api/hospital-ops/finance/revenue", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_claims", "GET", f"/api/hospital-ops/finance/claims", token=hospital_token, params={"hospitalId": hospital_id})

        tester.request("hospital_opd_appointments", "GET", "/api/hospital-ops/opd/appointments", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_appointments_insights", "GET", "/api/hospital-ops/opd/appointments/insights", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_doctors", "GET", "/api/hospital-ops/opd/doctors", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_doctors_coverage", "GET", "/api/hospital-ops/opd/doctors/coverage", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_consultations", "GET", "/api/hospital-ops/opd/consultations", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_consultations_insights", "GET", "/api/hospital-ops/opd/consultations/insights", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_opd_queue", "GET", "/api/hospital-ops/opd/queue", token=hospital_token, params={"hospitalId": hospital_id})

        tester.request("hospital_icu_patients", "GET", "/api/hospital-ops/icu/patients", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_icu_alerts", "GET", "/api/hospital-ops/icu/alerts", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_icu_vitals", "GET", "/api/hospital-ops/icu/vitals", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request(
            "hospital_icu_risk",
            "POST",
            "/api/hospital-ops/icu/risk",
            token=hospital_token,
            json_body={"oxygen": 92, "heartRate": 98},
        )

        tester.request("hospital_radiology_requests", "GET", "/api/hospital-ops/radiology/requests", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_radiology_reports", "GET", "/api/hospital-ops/radiology/reports", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_ot_surgeries", "GET", "/api/hospital-ops/ot/surgeries", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_ot_allocations", "GET", "/api/hospital-ops/ot/allocations", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_equipment", "GET", "/api/hospital-ops/equipment", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_emergency_intake", "GET", "/api/hospital-ops/emergency/intake", token=hospital_token, params={"hospitalId": hospital_id})
        tester.request("hospital_bed_allocations", "GET", "/api/hospital-ops/emergency/bed-allocation", token=hospital_token, params={"hospitalId": hospital_id})

        tester.request(
            "hospital_triage",
            "POST",
            "/api/hospital/triage",
            token=hospital_token,
            json_body={"symptoms": "shortness of breath", "severity_hint": "High"},
        )
        tester.request(
            "hospital_recovery",
            "POST",
            "/api/hospital/patient/recovery",
            token=hospital_token,
            json_body={"age": 45, "bmi": 24, "heart_rate": 78, "blood_pressure": 120, "diagnosis": "General", "treatment_type": "Standard"},
        )
        tester.request(
            "hospital_stay",
            "POST",
            "/api/hospital/patient/stay",
            token=hospital_token,
            json_body={"age": 45, "bmi": 24, "heart_rate": 78, "blood_pressure": 120, "diagnosis": "General", "treatment_type": "Standard"},
        )
        tester.request(
            "hospital_inventory_predict",
            "POST",
            "/api/hospital/inventory/predict",
            token=hospital_token,
            json_body={"name": "Ventilator", "quantity": 5, "category": "Equipment", "minThreshold": 2},
        )

        tester.request(
            "hospital_ai_eta",
            "POST",
            "/api/hosp/predict_eta",
            token=hospital_token,
            json_body={"distance_km": 8.5, "precipitation_mm": 0.2, "wind_kph": 10, "hour": 14},
        )
        tester.request(
            "hospital_ai_bed_forecast",
            "POST",
            "/api/hosp/predict_bed_forecast",
            token=hospital_token,
            json_body={"hospital_id": 1, "day": 2, "current_beds": 120},
        )
        tester.request(
            "hospital_ai_staff_alloc",
            "POST",
            "/api/hosp/predict_staff_allocation",
            token=hospital_token,
            json_body={"department": "ICU", "patient_load": "High", "shift": "Night"},
        )
        tester.request(
            "hospital_ai_disease_forecast",
            "POST",
            "/api/hosp/predict_disease_forecast",
            token=hospital_token,
            json_body={"disease": "Flu", "region": "Urban", "week": 12},
        )

        # Ambulance portal
        ambulance_token, ambulance_user = tester.login("ambulance", email="ambulance.002@lifelink.demo")
        ambulance_id = ambulance_user.get("id") or ambulance_user.get("_id")

        tester.request("ambulance_assignments", "GET", "/api/ambulance/assignments", token=ambulance_token)
        tester.request("ambulance_patient_info", "GET", "/api/ambulance/patient-info", token=ambulance_token)
        tester.request("ambulance_status", "GET", "/api/ambulance/emergency-status", token=ambulance_token)
        tester.request("ambulance_history", "GET", "/api/ambulance/history", token=ambulance_token)
        tester.request(
            "ambulance_route",
            "GET",
            "/v2/route",
            token=ambulance_token,
            params={
                "start_lat": 12.9716,
                "start_lng": 77.5946,
                "end_lat": 12.965,
                "end_lng": 77.59,
                "include_geometry": "false",
            },
        )

        _print_summary(tester.results)
        report_dir = Path(os.getenv("LIFELINK_SMOKE_REPORT_DIR", Path(__file__).resolve().parent))
        json_path, md_path = _write_reports(tester.results, report_dir)
        print(f"\nReport written: {json_path}")
        print(f"Report written: {md_path}")
        return 0 if all(item.ok for item in tester.results) else 1
    finally:
        tester.close()


if __name__ == "__main__":
    raise SystemExit(main())
