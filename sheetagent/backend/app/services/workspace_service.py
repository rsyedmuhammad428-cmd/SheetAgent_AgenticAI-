from pathlib import Path
from typing import Optional
import shutil
import aiofiles
from datetime import datetime, timezone

from app.config import settings
from app.models.schemas import WorkspaceItem, WorkspaceListing


class WorkspaceService:
    def _safe_path(self, *parts: str) -> Path:
        base = settings.workspace_path.resolve()
        path = (base / Path(*parts)).resolve()
        if not str(path).startswith(str(base)):
            raise PermissionError(f"Access denied: path outside workspace")
        return path

    def get_incoming(self) -> Path:  return self._safe_path("incoming")
    def get_processing(self) -> Path: return self._safe_path("processing")
    def get_extracted(self) -> Path:  return self._safe_path("extracted")
    def get_cleaned(self) -> Path:    return self._safe_path("cleaned")
    def get_excels(self) -> Path:     return self._safe_path("excels")
    def get_temp(self) -> Path:       return self._safe_path("temp")
    def get_logs(self) -> Path:       return self._safe_path("logs")

    async def save_upload(self, filename: str, content: bytes) -> Path:
        dest = self._safe_path("incoming", filename)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
        return dest

    def move_to_processing(self, source_path: Path, session_id: str) -> Path:
        dest_dir = self._safe_path("processing", session_id)
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / source_path.name
        shutil.copy2(source_path, dest)
        return dest

    def list_folder(self, folder_name: str) -> WorkspaceListing:
        folder = self._safe_path(folder_name)
        items = []
        if folder.exists():
            for item in sorted(folder.iterdir()):
                try:
                    stat = item.stat()
                    items.append(WorkspaceItem(
                        name=item.name,
                        path=str(item.relative_to(settings.workspace_path)),
                        is_dir=item.is_dir(),
                        size=stat.st_size if item.is_file() else None,
                        modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    ))
                except Exception:
                    pass
        return WorkspaceListing(folder=folder_name, items=items)

    def list_all_folders(self) -> dict:
        folders = ["incoming", "processing", "extracted", "cleaned",
                   "excels", "charts", "reports"]
        return {f: self.list_folder(f) for f in folders}


workspace_service = WorkspaceService()
