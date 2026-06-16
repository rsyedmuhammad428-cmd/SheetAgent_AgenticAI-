from pathlib import Path
import json

from app.models.state import AgentState, AgentStatus, FileType
from app.parsers.csv_parser import parse_csv, parse_excel
from app.services.ws_manager import ws_manager
from app.services.workspace_service import workspace_service
import logging

logger = logging.getLogger(__name__)


async def run_extraction_agent(state: AgentState) -> AgentState:
    if state.status == AgentStatus.ERROR:
        return state

    await ws_manager.send_log(state.session_id, "ExtractionAgent", "Extracting data from file...")

    try:
        file_path = Path(state.file_path)

        if state.file_type == FileType.CSV:
            rows, columns = parse_csv(file_path)
        elif state.file_type == FileType.EXCEL:
            rows, columns = parse_excel(file_path)
        elif state.file_type == FileType.TEXT:
            text = file_path.read_text(encoding="utf-8")
            rows = [{"content": line} for line in text.splitlines() if line.strip()]
            columns = ["content"]
        else:
            await ws_manager.send_log(
                state.session_id, "ExtractionAgent",
                f"File type {state.file_type} requires OCR — not yet implemented in Phase 1",
                level="warning"
            )
            state.extracted_data = []
            return state

        state.extracted_data = rows
        state.column_mapping = {col: col for col in columns}

        # Save extracted JSON
        extracted_dir = workspace_service.get_extracted()
        extracted_file = extracted_dir / f"{state.session_id}_extracted.json"
        extracted_file.write_text(json.dumps(rows[:100], indent=2, default=str))

        await ws_manager.send_log(
            state.session_id, "ExtractionAgent",
            f"Extracted {len(rows)} rows, {len(columns)} columns"
        )
        return state

    except Exception as e:
        logger.error(f"ExtractionAgent error: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        return state
