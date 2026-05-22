from app.models.state import AgentState, AgentStatus
from app.services.gemini_service import gemini_service
from app.services.ws_manager import ws_manager
import logging

logger = logging.getLogger(__name__)


async def run_planner_agent(state: AgentState) -> AgentState:
    if state.status == AgentStatus.ERROR:
        return state

    await ws_manager.send_log(state.session_id, "PlannerAgent", "Generating execution plan...")

    try:
        issues = {
            "suggestions_count": len(state.suggestions),
            "schema": state.schema_type.value if state.schema_type else "unknown",
            "rows": len(state.cleaned_data or []),
        }

        plan = await gemini_service.generate_plan(
            file_name=state.file_name or "unknown",
            schema_type=state.schema_type.value if state.schema_type else "generic",
            issues=issues,
        )
        state.plan = plan

        state.status = AgentStatus.AWAITING_APPROVAL

        await ws_manager.send_log(
            state.session_id, "PlannerAgent",
            f"Plan ready — {len(plan)} steps. Waiting for user approval."
        )

        await ws_manager.send_status(state.session_id, AgentStatus.AWAITING_APPROVAL.value)
        await ws_manager.send_suggestion(
            state.session_id,
            [s.model_dump() for s in state.suggestions]
        )

        return state

    except Exception as e:
        logger.error(f"PlannerAgent error: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        return state
