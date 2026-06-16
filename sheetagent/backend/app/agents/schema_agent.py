from app.models.state import AgentState, AgentStatus, SchemaType
from app.services.gemini_service import gemini_service
from app.services.ws_manager import ws_manager
import logging

logger = logging.getLogger(__name__)


async def run_schema_agent(state: AgentState) -> AgentState:
    if state.status == AgentStatus.ERROR or not state.cleaned_data:
        return state

    await ws_manager.send_log(state.session_id, "SchemaAgent", "Detecting data schema with Gemini...")

    try:
        columns = list(state.cleaned_data[0].keys()) if state.cleaned_data else []
        sample = state.cleaned_data[:5]

        result = await gemini_service.detect_schema(columns, sample)

        schema_str = result.get("schema_type", "generic")
        try:
            state.schema_type = SchemaType(schema_str)
        except ValueError:
            state.schema_type = SchemaType.GENERIC

        # Merge column mapping
        if result.get("column_mapping"):
            state.column_mapping.update(result["column_mapping"])

        # Add Gemini suggestions to our suggestion list
        for suggestion_text in result.get("suggested_improvements", []):
            from app.models.state import Suggestion
            import uuid
            state.suggestions.append(Suggestion(
                id=str(uuid.uuid4()),
                title="Data improvement suggestion",
                description=suggestion_text,
                action="gemini_suggestion",
            ))

        await ws_manager.send_log(
            state.session_id, "SchemaAgent",
            f"Schema detected: {state.schema_type.value} (confidence: {result.get('confidence', 0):.0%})"
        )
        return state

    except Exception as e:
        logger.error(f"SchemaAgent error: {e}")
        state.schema_type = SchemaType.GENERIC
        await ws_manager.send_log(state.session_id, "SchemaAgent", f"Schema detection failed, using generic: {e}", level="warning")
        return state
