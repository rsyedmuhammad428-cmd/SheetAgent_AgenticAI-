"""
Download Route — Phase 5
Serves generated Excel files securely from workspace/excels/.
Enforces sandbox — no path traversal allowed.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/excel/{filename}")
async def download_excel(filename: str):
    """
    Serve an Excel file from workspace/excels/.
    filename must be a plain filename with no path separators.
    """
    # Security: reject any path traversal attempt
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    excels_dir = settings.workspace_path / "excels"
    file_path = (excels_dir / filename).resolve()

    # Double-check it's still inside workspace
    if not str(file_path).startswith(str(excels_dir.resolve())):
        raise HTTPException(403, "Access denied")

    if not file_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    logger.info("file_download", filename=filename)

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/list")
async def list_downloads():
    """List all available Excel files for download."""
    excels_dir = settings.workspace_path / "excels"
    if not excels_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(excels_dir.glob("*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        files.append({
            "filename": f.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": stat.st_mtime,
            "download_url": f"/api/download/excel/{f.name}",
        })

    return {"files": files}
