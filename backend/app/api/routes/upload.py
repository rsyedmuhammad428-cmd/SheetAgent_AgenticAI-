from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid

from app.models.schemas import UploadResponse
from app.models.state import FileType
from app.services.workspace_service import workspace_service
from app.parsers.csv_parser import detect_file_type

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".csv", ".xlsx", ".xls", ".xlsm",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".tiff", ".webp",
    ".docx", ".doc",
    ".txt",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max size: 50MB")

    session_id = str(uuid.uuid4())
    safe_name = f"{session_id}_{file.filename}"
    saved_path = await workspace_service.save_upload(safe_name, content)

    detected = detect_file_type(saved_path)
    try:
        file_type = FileType(detected)
    except ValueError:
        file_type = FileType.UNKNOWN

    return UploadResponse(
        session_id=session_id,
        file_name=file.filename,
        file_type=file_type,
        file_path=str(saved_path),  # returned so frontend passes it with instruction
        message=f"File uploaded. Now tell me what to do with it.",
    )
