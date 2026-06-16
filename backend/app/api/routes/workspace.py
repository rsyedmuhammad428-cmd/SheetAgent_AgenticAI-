from fastapi import APIRouter
from app.services.workspace_service import workspace_service
from app.models.schemas import WorkspaceListing

router = APIRouter()


@router.get("/", response_model=dict)
async def list_workspace():
    result = workspace_service.list_all_folders()
    return {k: v.model_dump() for k, v in result.items()}


@router.get("/{folder}", response_model=WorkspaceListing)
async def list_folder(folder: str):
    return workspace_service.list_folder(folder)
