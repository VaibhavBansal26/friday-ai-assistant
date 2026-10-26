from collections.abc import Callable
from pathlib import Path
from typing import Any

from friday.domain.models import ExecutionStatus, FridayAgentState
from friday.services.agents import route_request
from friday.services.capabilities import CapabilityCatalog


NODE_ORDER = (
    "ingest_request",
    "validate_transcript",
    "classify_intent",
    "classify_risk",
    "load_user_policy",
    "resolve_verified_facts",
    "detect_missing_information",
    "retrieve_context",
    "scan_prompt_injection",
    "select_agent",
    "create_plan",
    "validate_plan",
    "request_approval",
    "wait_for_approval",
    "execute_tool",
    "record_tool_result",
    "safe_retry_decision",
    "verify_outcome",
    "compose_response",
    "persist_governed_memory",
)


def _stage(
    active_agent: str,
    status: ExecutionStatus,
    extra: Callable[[FridayAgentState], dict[str, Any]] | None = None,
) -> Callable[[FridayAgentState], dict[str, Any]]:
    def node(state: FridayAgentState) -> dict[str, Any]:
        update: dict[str, Any] = {
            "active_agent": active_agent,
            "execution_status": status,
        }
        if extra:
            update.update(extra(state))
        return update

    return node


def _approval_state(state: FridayAgentState) -> dict[str, Any]:
    needs_approval = any(request.risk >= 2 for request in state.approval_requests)
    return {
        "execution_status": (
            ExecutionStatus.WAITING_APPROVAL if needs_approval else ExecutionStatus.ACTING
        )
    }


def _plan_state(state: FridayAgentState) -> dict[str, Any]:
    if state.plan:
        return {}
    return {
        "plan": [
            {"step": "Understand and verify the request", "status": "completed"},
            {"step": "Execute within policy", "status": "pending"},
            {"step": "Verify the outcome", "status": "pending"},
        ],
        "current_step": 1,
    }


def _agent_selection_state(state: FridayAgentState) -> dict[str, Any]:
    route = route_request(state.current_goal)
    readiness = CapabilityCatalog(Path.cwd()).readiness(route)
    return {
        "active_agent": route.agent,
        "execution_status": ExecutionStatus.PLANNING,
        "content_context": {
            **(state.content_context or {}),
            "intent": route.intent,
            "selected_agent": route.agent,
            "required_tool_group": route.tool_group,
            "risk": int(route.risk),
            "routing_confidence": route.confidence,
            "capability_ready": readiness.ready,
            "capability_reason": readiness.reason,
            "approval_required": readiness.approval_required,
        },
    }


def _final_state(state: FridayAgentState) -> dict[str, Any]:
    verified = bool(state.verification_result and state.verification_result.verified)
    return {
        "execution_status": ExecutionStatus.COMPLETED if verified else ExecutionStatus.BLOCKED,
        "final_response": state.final_response
        or (
            "Completed with verified evidence."
            if verified
            else "I do not have enough verified information to claim completion."
        ),
    }


NODE_HANDLERS: dict[str, Callable[[FridayAgentState], dict[str, Any]]] = {
    "ingest_request": _stage("supervisor", ExecutionStatus.UNDERSTANDING),
    "validate_transcript": _stage("voice", ExecutionStatus.UNDERSTANDING),
    "classify_intent": _stage("intent-classification", ExecutionStatus.UNDERSTANDING),
    "classify_risk": _stage("risk-classification", ExecutionStatus.UNDERSTANDING),
    "load_user_policy": _stage("security-policy", ExecutionStatus.PLANNING),
    "resolve_verified_facts": _stage("knowledge-retrieval", ExecutionStatus.PLANNING),
    "detect_missing_information": _stage("supervisor", ExecutionStatus.PLANNING),
    "retrieve_context": _stage("knowledge-retrieval", ExecutionStatus.PLANNING),
    "scan_prompt_injection": _stage("security-policy", ExecutionStatus.PLANNING),
    "select_agent": _agent_selection_state,
    "create_plan": _stage("task-manager", ExecutionStatus.PLANNING, _plan_state),
    "validate_plan": _stage("security-policy", ExecutionStatus.PLANNING),
    "request_approval": _stage("supervisor", ExecutionStatus.PLANNING, _approval_state),
    "wait_for_approval": _stage("supervisor", ExecutionStatus.WAITING_APPROVAL, _approval_state),
    "execute_tool": _stage("supervisor", ExecutionStatus.ACTING),
    "record_tool_result": _stage("verification", ExecutionStatus.ACTING),
    "safe_retry_decision": _stage("security-policy", ExecutionStatus.ACTING),
    "verify_outcome": _stage("verification", ExecutionStatus.VERIFYING),
    "compose_response": _stage("supervisor", ExecutionStatus.VERIFYING, _final_state),
    "persist_governed_memory": _stage("personal-memory", ExecutionStatus.COMPLETED),
}


def build_graph():
    """Build the 20-node safety-first supervisor graph."""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(FridayAgentState)
    for name in NODE_ORDER:
        graph.add_node(name, NODE_HANDLERS[name])
    graph.set_entry_point(NODE_ORDER[0])
    for current, following in zip(NODE_ORDER, NODE_ORDER[1:]):
        graph.add_edge(current, following)
    graph.add_edge(NODE_ORDER[-1], END)
    return graph.compile()
