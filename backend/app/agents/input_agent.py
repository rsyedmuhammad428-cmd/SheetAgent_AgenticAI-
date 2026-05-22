from app.models.state import AgentState, AgentStatus, FileType
from app.parsers.csv_parser import detect_file_type
from app.services.workspace_service import workspace_service
from app.services.ws_manager import ws_manager
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


async def run_input_agent(state: AgentState) -> AgentState:
    await ws_manager.send_log(state.session_id, "InputAgent", f"Analyzing file: {state.file_name}")

    try:
        file_path = Path(state.file_path)
        if not file_path.exists():
            state.error = f"File not found: {state.file_path}"
            state.status = AgentStatus.ERROR
            return state

        detected = detect_file_type(file_path)
        state.file_type = FileType(detected)

        proc_path = workspace_service.move_to_processing(file_path, state.session_id)
        state.file_path = str(proc_path)

        await ws_manager.send_log(
            state.session_id, "InputAgent",
            f"File type detected: {state.file_type.value} — moved to processing"
        )

        if state.file_type == FileType.UNKNOWN:
            state.error = "Unsupported file type"
            state.status = AgentStatus.ERROR
            return state

        if state.file_type in [FileType.PDF, FileType.IMAGE]:
            await ws_manager.send_log(
                state.session_id, "InputAgent",
                "OCR pipeline required — scheduled for Phase 3. Using text extraction for now.",
                level="warning"
            )

        state.status = AgentStatus.RUNNING
        return state

    except Exception as e:
        logger.error(f"InputAgent error: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        return state
