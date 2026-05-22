from pydantic import BaseModel
from typing import Any, Optional
from app.models.state import AgentStatus, FileType, SchemaType, Suggestion, ExecutionStep


class UploadResponse(BaseModel):
    session_id: str
    file_name: str
    file_type: FileType
    file_path: str
    message: str


class AgentRunRequest(BaseModel):
    session_id: str
    user_message: Optional[str] = None
    command: Optional[str] = None


class ApprovalRequest(BaseModel):
    session_id: str
    suggestion_id: str
    approved: bool
    custom_params: Optional[dict] = None


class AgentStateResponse(BaseModel):
    session_id: str
    status: AgentStatus
    file_type: Optional[FileType] = None
    schema_type: Optional[SchemaType] = None
    plan: list[str] = []
    suggestions: list[Suggestion] = []
    execution_steps: list[ExecutionStep] = []
    output_excel_path: Optional[str] = None
    error: Optional[str] = None


class WorkspaceItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified: Optional[str] = None


class WorkspaceListing(BaseModel):
    folder: str
    items: list[WorkspaceItem]


class WSMessage(BaseModel):
    type: str
    session_id: str
    data: Any
