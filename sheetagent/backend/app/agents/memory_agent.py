"""
Memory Agent — Phase 4
Two responsibilities:
1. RECALL  — at start of each session, load preferences + history context
2. LEARN   — after each session, infer new preferences from what happened

Gemini is used to:
  - parse natural language like "reuse last week's format"
  - infer preferences from repeated patterns across sessions
"""
from app.models.state import AgentState
from app.services.memory_service import (
    get_preferences, save_session, get_recent_sessions,
    get_snippets, save_snippet
)
from app.services.gemini_service import gemini_service
from app.services.ws_manager import ws_manager
import json
import logging

logger = logging.getLogger(__name__)


# ── RECALL — runs at session start ────────────────────────────────────────────

async def run_recall_agent(state: AgentState) -> AgentState:
    """
    Load user preferences and recent session context.
    Injects into state so downstream agents can use them.
    """
    await ws_manager.send_log(state.session_id, "MemoryAgent", "Loading user preferences and history...")

    try:
        prefs = await get_preferences()
        recent = await get_recent_sessions(limit=5)
        snippets = await get_snippets()

        state.user_preferences = prefs
        state.session_history = recent
        state.memory_snippets = snippets

        if recent:
            last = recent[0]
            await ws_manager.send_log(
                state.session_id, "MemoryAgent",
                f"Found {len(recent)} past session(s). Last: {last.get('file_name')} ({last.get('schema_type')})"
            )

        # Parse user message for history references
        if state.user_message:
            context = await _resolve_history_reference(state.user_message, recent, prefs)
            if context:
                state.memory_context = context
                await ws_manager.send_log(
                    state.session_id, "MemoryAgent",
                    f"History reference resolved: {context.get('summary', '')}"
                )

        return state

    except Exception as e:
        logger.error(f"MemoryAgent recall error: {e}")
        await ws_manager.send_log(state.session_id, "MemoryAgent", f"Memory recall failed: {e}", level="warning")
        return state


async def _resolve_history_reference(
    user_message: str,
    recent_sessions: list[dict],
    prefs: dict
) -> dict | None:
    """
    If user says "reuse last week's format" or "same as invoice template",
    resolve what they mean and return applicable context.
    """
    history_keywords = ["last", "previous", "reuse", "same as", "like before", "again"]
    if not any(kw in user_message.lower() for kw in history_keywords):
        return None

    prompt = f"""
The user said: "{user_message}"

Recent sessions:
{json.dumps(recent_sessions[:3], indent=2)}

Current preferences:
{json.dumps(prefs, indent=2)}

The user seems to be referencing a past session or format.
Identify what they want to reuse and return JSON:
{{
  "summary": "One sentence explaining what was resolved",
  "apply_session_id": "session_id to reuse, or null",
  "override_preferences": {{
    "key": "value"
  }}
}}

If nothing specific can be resolved, return null.
"""
    try:
        result = await gemini_service.analyze_json(prompt)
        return result if isinstance(result, dict) else None
    except Exception:
        return None


# ── LEARN — runs after session completes ─────────────────────────────────────

async def run_learn_agent(state: AgentState) -> AgentState:
    """
    After a completed session, infer and store user preferences.
    """
    await ws_manager.send_log(state.session_id, "MemoryAgent", "Learning from session...")

    try:
        # Save session to history
        session_data = {
            "session_id": state.session_id,
            "file_name": state.file_name,
            "file_type": state.file_type.value if state.file_type else None,
            "schema_type": state.schema_type.value if state.schema_type else None,
            "row_count": len(state.cleaned_data or []),
            "col_count": len((state.cleaned_data or [{}])[0].keys()) if state.cleaned_data else 0,
            "status": state.status.value,
            "output_path": state.output_excel_path,
            "plan_steps": state.plan,
            "column_names": list((state.cleaned_data or [{}])[0].keys()) if state.cleaned_data else [],
            "quality_score": state.reflection_report.get("score") if state.reflection_report else None,
        }
        await save_session(session_data)

        # Use Gemini to infer preferences from this session
        inferred = await _infer_preferences(state, session_data)
        for key, value in inferred.items():
            await save_snippet(
                key=key,
                value=str(value),
                source="inferred",
                confidence=0.75,
            )

        await ws_manager.send_log(
            state.session_id, "MemoryAgent",
            f"Session saved. {len(inferred)} preference(s) learned."
        )
        return state

    except Exception as e:
        logger.error(f"MemoryAgent learn error: {e}")
        return state


async def _infer_preferences(state: AgentState, session_data: dict) -> dict:
    """Ask Gemini to infer user preferences from the session."""
    prompt = f"""
Analyze this completed data processing session and infer user preferences.

Session data:
{json.dumps(session_data, indent=2)}

Column names used: {session_data.get('column_names', [])}
Schema type: {session_data.get('schema_type')}

Infer preferences the user likely has based on their data patterns.
Return JSON of key-value pairs to remember, e.g.:
{{
  "common_schema": "invoice",
  "typical_row_count": "500-1000",
  "uses_currency_columns": "true",
  "preferred_date_columns": "invoice_date, due_date"
}}

Only include things that are genuinely useful to remember for future sessions.
Return an empty object if nothing notable.
"""
    try:
        result = await gemini_service.analyze_json(prompt)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}
