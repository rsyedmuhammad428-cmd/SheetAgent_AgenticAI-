from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import AgentRunRequest, ApprovalRequest, AgentStateResponse
from app.models.state import AgentState, AgentStatus
from app.services.session_store import session_store
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_state(session_id: str) -> AgentState:
    data = await session_store.get(session_id)
    if not data:
        raise HTTPException(404, f"Session not found: {session_id}")
    return AgentState(**data)


async def _save_state(state: AgentState):
    await session_store.set(state.session_id, state.model_dump())


@router.post("/run", response_model=AgentStateResponse)
async def run_agent(body: AgentRunRequest, background_tasks: BackgroundTasks):
    from app.services.workspace_service import workspace_service

    incoming_files = list(workspace_service.get_incoming().glob(f"{body.session_id}_*"))
    if not incoming_files:
        raise HTTPException(404, f"No uploaded file for session {body.session_id}")

    file_path = incoming_files[0]
    state = AgentState(
        session_id=body.session_id,
        file_path=str(file_path),
        file_name=file_path.name.replace(f"{body.session_id}_", ""),
        user_message=body.user_message,
    )
    await _save_state(state)
    background_tasks.add_task(_run_pipeline_bg, body.session_id, state)

    return AgentStateResponse(session_id=body.session_id, status=AgentStatus.RUNNING)


async def _run_pipeline_bg(session_id: str, state: AgentState):
    try:
        from app.agents.graph import run_pipeline
        result = await run_pipeline(state)
        await _save_state(result)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        state.status = AgentStatus.ERROR
        state.error = str(e)
        await _save_state(state)


@router.post("/approve-all", response_model=AgentStateResponse)
async def approve_all(session_id: str, background_tasks: BackgroundTasks):
    state = await _get_state(session_id)
    for s in state.suggestions:
        s.approved = True
    state.status = AgentStatus.APPROVED
    await _save_state(state)
    background_tasks.add_task(_run_excel_bg, session_id, state)
    return AgentStateResponse(session_id=session_id, status=state.status, plan=state.plan)


@router.post("/approve", response_model=AgentStateResponse)
async def approve_suggestion(body: ApprovalRequest, background_tasks: BackgroundTasks):
    state = await _get_state(body.session_id)
    for s in state.suggestions:
        if s.id == body.suggestion_id:
            s.approved = body.approved
    if body.approved:
        state.status = AgentStatus.APPROVED
        background_tasks.add_task(_run_excel_bg, body.session_id, state)
    else:
        state.status = AgentStatus.REJECTED
    await _save_state(state)
    return AgentStateResponse(session_id=state.session_id, status=state.status,
                               plan=state.plan, suggestions=state.suggestions)


async def _run_excel_bg(session_id: str, state: AgentState):
    try:
        from app.agents.graph import run_post_approval_phase
        result = await run_post_approval_phase(state)
        await _save_state(result)
    except Exception as e:
        logger.error(f"Excel gen error: {e}", exc_info=True)
        state.status = AgentStatus.ERROR
        state.error = str(e)
        await _save_state(state)


@router.get("/{session_id}/state", response_model=AgentStateResponse)
async def get_state(session_id: str):
    state = await _get_state(session_id)
    return AgentStateResponse(
        session_id=state.session_id,
        status=state.status,
        file_type=state.file_type,
        schema_type=state.schema_type,
        plan=state.plan,
        suggestions=state.suggestions,
        execution_steps=state.execution_steps,
        output_excel_path=state.output_excel_path,
        error=state.error,
    )
