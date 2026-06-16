from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.agents.formula_agent import run_formula_agent
from app.agents.analytics_agent import run_analytics_agent, simple_forecast
from app.agents.visualization_agent import run_visualization_agent
from app.agents.reflection_agent import run_reflection_agent
from app.services.diff_service import compute_diff, summarize_diff

router = APIRouter()

# Shared session store reference (imported from agent route in phase 1)
# In production use Redis; here we use a module-level dict
_sessions: dict = {}


def set_sessions_store(store: dict):
    global _sessions
    _sessions = store


# ── Formula ─────────────────────────────────────────────────────────────────

class FormulaRequest(BaseModel):
    session_id: str
    formulas: list[str]  # natural language formula requests


class FormulaResponse(BaseModel):
    session_id: str
    applied_count: int
    message: str


@router.post("/formula", response_model=FormulaResponse)
async def apply_formulas(request: FormulaRequest, background_tasks: BackgroundTasks):
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {request.session_id}")

    background_tasks.add_task(_run_formulas, request.session_id, request.formulas)
    return FormulaResponse(
        session_id=request.session_id,
        applied_count=len(request.formulas),
        message=f"Processing {len(request.formulas)} formula(s)..."
    )


async def _run_formulas(session_id: str, formulas: list[str]):
    state = _sessions.get(session_id)
    if state:
        result = await run_formula_agent(state, formulas)
        _sessions[session_id] = result


# ── Analytics ────────────────────────────────────────────────────────────────

class AnalyticsRequest(BaseModel):
    session_id: str
    question: str


class AnalyticsResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    data: dict = {}


@router.post("/analytics", response_model=AnalyticsResponse)
async def ask_analytics(request: AnalyticsRequest):
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {request.session_id}")

    result = await run_analytics_agent(state, request.question)
    return AnalyticsResponse(
        session_id=request.session_id,
        question=result.question,
        answer=result.answer,
        data=result.data,
    )


# ── Charts ───────────────────────────────────────────────────────────────────

class ChartRequest(BaseModel):
    session_id: str
    charts: Optional[list[str]] = None  # None = auto-detect


@router.post("/charts")
async def generate_charts(request: ChartRequest, background_tasks: BackgroundTasks):
    state = _sessions.get(request.session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {request.session_id}")

    background_tasks.add_task(_run_charts, request.session_id, request.charts)
    return {"session_id": request.session_id, "message": "Chart generation started..."}


async def _run_charts(session_id: str, chart_requests: list | None):
    state = _sessions.get(session_id)
    if state:
        result = await run_visualization_agent(state, chart_requests)
        _sessions[session_id] = result


# ── Reflection ───────────────────────────────────────────────────────────────

@router.post("/reflect")
async def run_reflection(session_id: str):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {session_id}")

    _, report = await run_reflection_agent(state)
    return {
        "session_id": session_id,
        "report": report.to_dict(),
    }


# ── Diff ─────────────────────────────────────────────────────────────────────

@router.get("/diff/{session_id}")
async def get_diff(session_id: str, limit: int = 100):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {session_id}")

    if not state.extracted_data or not state.cleaned_data:
        return {"session_id": session_id, "diff": [], "summary": {}}

    diff = compute_diff(state.extracted_data, state.cleaned_data, max_diffs=limit)
    summary = summarize_diff(diff)

    return {
        "session_id": session_id,
        "diff": [d.model_dump() for d in diff],
        "summary": summary,
    }


# ── Forecast ─────────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    values: list[float]
    periods: int = 3


@router.post("/forecast")
async def forecast(request: ForecastRequest):
    forecasted = simple_forecast(request.values, request.periods)
    return {"forecasted": forecasted, "periods": request.periods}
