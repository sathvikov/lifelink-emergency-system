from __future__ import annotations

from typing import Any, Dict, List


def execute_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    executed = []
    for action in actions:
        action_type = action.get("type")
        result = {
            "type": action_type,
            "status": "executed",
            "meta": action.get("meta") or {},
        }
        if action_type == "resource_allocation":
            result["summary"] = "Resource allocation queued"
        elif action_type == "hospital_notify":
            result["summary"] = "Hospital alerts dispatched"
        elif action_type == "ambulance_dispatch":
            result["summary"] = "Ambulance dispatch initiated"
        elif action_type == "workflow_automation":
            result["summary"] = "Workflow tasks orchestrated"
        elif action_type == "decision":
            result["summary"] = action.get("summary") or "Decision executed"
        else:
            result["summary"] = "Action executed"
        executed.append(result)
    return executed
