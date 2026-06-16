from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from pathlib import Path
from app.agents.ocr_agent import run_ocr_agent
from app.models.state import AgentState, FileType
from app.services.workspace_service import workspace_service
from app.parsers.pdf_parser import is_searchable_pdf, get_pdf_page_count
from app.parsers.image_preprocessor import preprocess_for_ocr
import uuid

router = APIRouter()
_sessions: dict = {}


def set_sessions_store(store: dict):
    global _sessions
    _sessions = store


class OCRStatusResponse(BaseModel):
    session_id: str
    file_type: str
    is_searchable: bool | None = None
    page_count: int | None = None
    rows_extracted: int
    ocr_engine_used: str | None = None
    status: str


@router.get("/status/{session_id}", response_model=OCRStatusResponse)
async def get_ocr_status(session_id: str):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {session_id}")

    is_searchable = None
    page_count = None
    if state.file_type == FileType.PDF and state.file_path:
        fp = Path(state.file_path)
        if fp.exists():
            is_searchable, _ = is_searchable_pdf(fp)
            page_count = get_pdf_page_count(fp)

    return OCRStatusResponse(
        session_id=session_id,
        file_type=state.file_type.value if state.file_type else "unknown",
        is_searchable=is_searchable,
        page_count=page_count,
        rows_extracted=len(state.extracted_data or []),
        status=state.status.value,
    )


@router.post("/retry/{session_id}")
async def retry_ocr(session_id: str, background_tasks: BackgroundTasks):
    """Manually re-trigger OCR for a session."""
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, f"Session not found: {session_id}")

    if state.file_type not in [FileType.PDF, FileType.IMAGE]:
        raise HTTPException(400, "OCR only applies to PDF and image files")

    background_tasks.add_task(_run_ocr_background, session_id, state)
    return {"session_id": session_id, "message": "OCR retry started"}


async def _run_ocr_background(session_id: str, state: AgentState):
    result = await run_ocr_agent(state)
    _sessions[session_id] = result


@router.post("/preview")
async def preview_ocr(file: UploadFile = File(...)):
    """
    Quick OCR preview without creating a full session.
    Returns first 10 extracted rows.
    """
    content = await file.read()
    temp_id = str(uuid.uuid4())[:8]
    temp_path = workspace_service.get_temp() / f"preview_{temp_id}_{file.filename}"
    temp_path.write_bytes(content)

    try:
        from app.parsers.ocr_engine import ocr_engine
        from app.parsers.image_preprocessor import preprocess_for_ocr

        ext = Path(file.filename).suffix.lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".tiff"]:
            preprocessed = preprocess_for_ocr(temp_path)
            tables = ocr_engine.extract_tables_from_image(preprocessed)
            rows = []
            for table in tables:
                rows.extend(table.to_dicts()[:10])
            return {"rows": rows[:10], "engine": "easyocr+img2table"}

        elif ext == ".pdf":
            from app.parsers.pdf_parser import is_searchable_pdf, extract_tables_from_searchable_pdf
            searchable, _ = is_searchable_pdf(temp_path)
            if searchable:
                tables = extract_tables_from_searchable_pdf(temp_path)
                rows = tables[0][:10] if tables else []
                return {"rows": rows, "engine": "pdfplumber", "searchable": True}
            else:
                return {"rows": [], "engine": "easyocr", "searchable": False,
                        "message": "Scanned PDF — full processing required"}
        else:
            return {"rows": [], "error": "Unsupported file type for preview"}

    finally:
        temp_path.unlink(missing_ok=True)
