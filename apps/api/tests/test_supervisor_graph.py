from uuid import uuid4

from friday.domain.models import ExecutionStatus, FridayAgentState
from friday.graph.supervisor import NODE_HANDLERS, NODE_ORDER, build_graph


def state():
    return FridayAgentState(
        user_id=uuid4(),
        conversation_id=uuid4(),
        session_id=uuid4(),
        current_goal="Verify the graph",
    )


def test_supervisor_contains_exactly_20_specified_nodes():
    assert len(NODE_ORDER) == 20
    assert set(NODE_HANDLERS) == set(NODE_ORDER)
    compiled = build_graph().get_graph()
    assert set(NODE_ORDER).issubset(compiled.nodes)


def test_plan_node_creates_user_safe_plan_without_private_reasoning():
    update = NODE_HANDLERS["create_plan"](state())
    assert len(update["plan"]) == 3
    assert all("step" in item and "status" in item for item in update["plan"])


def test_unverified_final_state_never_claims_completion():
    update = NODE_HANDLERS["compose_response"](state())
    assert update["execution_status"] == ExecutionStatus.BLOCKED
    assert "do not have enough verified information" in update["final_response"]


def test_select_agent_uses_capability_registry():
    item = state()
    item.current_goal = "Create a YouTube Shorts video"
    update = NODE_HANDLERS["select_agent"](item)
    assert update["active_agent"] == "youtube"
    assert update["content_context"]["required_tool_group"] == "media"
