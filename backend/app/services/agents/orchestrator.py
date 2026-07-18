from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from app.services.agents.action_executor import execute_actions
from app.services.agents.llm_client import generate_text


class AgentState(TypedDict):
    event: Dict[str, Any]
    notes: List[str]
    actions: List[Dict[str, Any]]
    executed_actions: List[Dict[str, Any]]
    shared: Dict[str, Any]
    conversation: Dict[str, Any]
    memory_id: str | None


def _append(state: AgentState, note: str) -> AgentState:
    state["notes"].append(note)
    return state


def health_monitor_agent(state: AgentState) -> AgentState:
    state["shared"]["health_status"] = "stable"
    return _append(state, "Health Monitoring Agent: vitals analyzed")


def risk_prediction_agent(state: AgentState) -> AgentState:
    state["shared"]["risk_score"] = state["event"].get("risk_score", 0.42)
    return _append(state, "Risk Prediction Agent: risk scored")


def emergency_detection_agent(state: AgentState) -> AgentState:
    state["shared"]["triage_level"] = state["event"].get("severity", "Medium")
    return _append(state, "Emergency Detection Agent: triage completed")


def resource_allocation_agent(state: AgentState) -> AgentState:
    state["actions"].append({"type": "resource_allocation", "status": "queued"})
    return _append(state, "Resource Allocation Agent: capacity checked")


def hospital_coordination_agent(state: AgentState) -> AgentState:
    state["actions"].append({"type": "hospital_notify", "status": "queued"})
    return _append(state, "Hospital Coordination Agent: alerts prepared")


def ambulance_dispatch_agent(state: AgentState) -> AgentState:
    state["actions"].append({"type": "ambulance_dispatch", "status": "queued"})
    return _append(state, "Ambulance Dispatch Agent: route planned")


def government_insight_agent(state: AgentState) -> AgentState:
    state["shared"]["gov_signal"] = "monitor"
    return _append(state, "Government Insight Agent: trend signals captured")


def workflow_automation_agent(state: AgentState) -> AgentState:
    state["actions"].append({"type": "workflow_automation", "status": "queued"})
    return _append(state, "Workflow Automation Agent: tasks orchestrated")


def conversational_ai_agent(state: AgentState) -> AgentState:
    query = state["event"].get("query") or state["event"].get("message")
    if not query:
        return _append(state, "Conversational AI Agent: no prompt")

    response = generate_text(
        prompt=f"User query: {query}\nProvide a concise response:",
        system_prompt="You are LifeLink Assist. Respond clearly and empathetically.",
    )
    state["conversation"] = {"query": query, "response": response}
    return _append(state, "Conversational AI Agent: response prepared")


def decision_agent(state: AgentState) -> AgentState:
    summary = "\n".join(state["notes"])
    decision = generate_text(
        prompt=f"Summarize and decide next actions for: {state['event']}. Notes: {summary}",
        system_prompt="You are the Decision Agent for LifeLink. Produce concise next actions.",
    )
    state["actions"].append({"type": "decision", "summary": decision})
    return _append(state, "Decision Agent: decision issued")


def execution_agent(state: AgentState) -> AgentState:
    if state["event"].get("execute") is False:
        return _append(state, "Execution Agent: execution skipped")
    if not state["actions"]:
        return _append(state, "Execution Agent: no actions")
    state["executed_actions"] = execute_actions(state["actions"])
    return _append(state, "Execution Agent: actions executed")


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("health", health_monitor_agent)
    graph.add_node("risk", risk_prediction_agent)
    graph.add_node("emergency", emergency_detection_agent)
    graph.add_node("resources", resource_allocation_agent)
    graph.add_node("hospital", hospital_coordination_agent)
    graph.add_node("ambulance", ambulance_dispatch_agent)
    graph.add_node("government", government_insight_agent)
    graph.add_node("workflow", workflow_automation_agent)
    graph.add_node("conversational", conversational_ai_agent)
    graph.add_node("decision", decision_agent)
    graph.add_node("execution", execution_agent)

    graph.set_entry_point("health")
    graph.add_edge("health", "risk")
    graph.add_edge("risk", "emergency")
    graph.add_edge("emergency", "resources")
    graph.add_edge("resources", "hospital")
    graph.add_edge("hospital", "ambulance")
    graph.add_edge("ambulance", "government")
    graph.add_edge("government", "workflow")
    graph.add_edge("workflow", "conversational")
    graph.add_edge("conversational", "decision")
    graph.add_edge("decision", "execution")
    graph.add_edge("execution", END)

    return graph.compile()


def run_decision_workflow(event: Dict[str, Any], memory_id: str | None = None) -> AgentState:
    graph = build_graph()
    initial: AgentState = {
        "event": event,
        "notes": [],
        "actions": [],
        "executed_actions": [],
        "shared": {},
        "conversation": {},
        "memory_id": memory_id,
    }
    return graph.invoke(initial)
