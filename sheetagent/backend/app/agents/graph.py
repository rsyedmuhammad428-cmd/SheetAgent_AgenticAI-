from langgraph.graph import StateGraph, END
from app.models.state import AgentState, AgentStatus, FileType
import logging

logger = logging.getLogger(__name__)


def route_after_input(state: AgentState) -> str:
    if state.status == AgentStatus.ERROR:
        return "error_end"
    if state.file_type in [FileType.PDF, FileType.IMAGE]:
        return "ocr"
    return "extraction"


def route_after_ocr(state: AgentState) -> str:
    if state.status == AgentStatus.ERROR:
        return "error_end"
    return "cleaning"


async def recall_node(state: AgentState) -> AgentState:
    try:
        from app.agents.memory_agent import run_recall_agent
        return await run_recall_agent(state)
    except Exception as e:
        logger.warning(f"Memory recall skipped: {e}")
        return state


async def input_node(state: AgentState) -> AgentState:
    from app.agents.input_agent import run_input_agent
    return await run_input_agent(state)


async def ocr_node(state: AgentState) -> AgentState:
    try:
        from app.agents.ocr_agent import run_ocr_agent
        return await run_ocr_agent(state)
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        return state


async def extraction_node(state: AgentState) -> AgentState:
    if state.extracted_data:
        return state
    from app.agents.extraction_agent import run_extraction_agent
    return await run_extraction_agent(state)


async def cleaning_node(state: AgentState) -> AgentState:
    from app.agents.cleaning_agent import run_cleaning_agent
    return await run_cleaning_agent(state)


async def schema_node(state: AgentState) -> AgentState:
    from app.agents.schema_agent import run_schema_agent
    return await run_schema_agent(state)


async def planner_node(state: AgentState) -> AgentState:
    from app.agents.planner_agent import run_planner_agent
    return await run_planner_agent(state)


async def excel_formula_node(state: AgentState) -> AgentState:
    from app.agents.excel_agent import run_excel_agent
    state = await run_excel_agent(state)
    if state.status != AgentStatus.ERROR and state.pending_formulas:
        try:
            from app.agents.formula_agent import run_formula_agent
            state = await run_formula_agent(state, state.pending_formulas)
        except Exception as e:
            logger.warning(f"Formula agent skipped: {e}")
    return state


async def visualize_reflect_node(state: AgentState) -> AgentState:
    if state.status == AgentStatus.ERROR:
        return state

    # Charts
    try:
        from app.agents.visualization_agent import run_visualization_agent
        charts = state.pending_charts or ([] if state.user_preferences.get("always_generate_charts") else None)
        state = await run_visualization_agent(state, charts)
    except Exception as e:
        logger.warning(f"Visualization skipped: {e}")

    # Reflection
    try:
        from app.agents.reflection_agent import run_reflection_agent
        from app.services.ws_manager import ws_manager
        state, report = await run_reflection_agent(state)
        state.reflection_report = report.to_dict()
        await ws_manager.broadcast(state.session_id, {
            "type": "reflection",
            "session_id": state.session_id,
            "data": report.to_dict(),
        })
    except Exception as e:
        logger.warning(f"Reflection skipped: {e}")

    return state


async def learn_node(state: AgentState) -> AgentState:
    try:
        from app.agents.memory_agent import run_learn_agent
        return await run_learn_agent(state)
    except Exception as e:
        logger.warning(f"Memory learn skipped: {e}")
        return state


async def error_node(state: AgentState) -> AgentState:
    from app.services.ws_manager import ws_manager
    await ws_manager.send_status(state.session_id, AgentStatus.ERROR.value)
    return state


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("recall",             recall_node)
    graph.add_node("input",              input_node)
    graph.add_node("ocr",                ocr_node)
    graph.add_node("extraction",         extraction_node)
    graph.add_node("cleaning",           cleaning_node)
    graph.add_node("schema",             schema_node)
    graph.add_node("planner",            planner_node)
    graph.add_node("excel_formula",      excel_formula_node)
    graph.add_node("visualize_reflect",  visualize_reflect_node)
    graph.add_node("learn",              learn_node)
    graph.add_node("error_end",          error_node)

    graph.set_entry_point("recall")
    graph.add_edge("recall", "input")

    graph.add_conditional_edges("input", route_after_input, {
        "ocr":        "ocr",
        "extraction": "extraction",
        "error_end":  "error_end",
    })
    graph.add_conditional_edges("ocr", route_after_ocr, {
        "cleaning":  "cleaning",
        "error_end": "error_end",
    })

    graph.add_edge("extraction", "cleaning")
    graph.add_edge("cleaning",   "schema")
    graph.add_edge("schema",     "planner")
    graph.add_edge("planner",    END)  # pause for approval

    graph.add_edge("excel_formula",     "visualize_reflect")
    graph.add_edge("visualize_reflect", "learn")
    graph.add_edge("learn",             END)
    graph.add_edge("error_end",         END)

    return graph.compile()


async def run_pipeline(state: AgentState) -> AgentState:
    g = build_graph()
    result = await g.ainvoke(state)
    return AgentState(**result)


async def run_post_approval_phase(state: AgentState) -> AgentState:
    state = await excel_formula_node(state)
    state = await visualize_reflect_node(state)
    state = await learn_node(state)
    return state
