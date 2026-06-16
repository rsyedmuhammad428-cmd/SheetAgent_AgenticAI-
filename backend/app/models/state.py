from typing import Any, Optional
from pydantic import BaseModel
from enum import Enum


class AgentStatus(str, Enum):
    PENDING           = "pending"
    RUNNING           = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED          = "approved"
    REJECTED          = "rejected"
    COMPLETE          = "complete"
    ERROR             = "error"


class FileType(str, Enum):
    CSV     = "csv"
    EXCEL   = "excel"
    PDF     = "pdf"
    IMAGE   = "image"
    TEXT    = "text"
    UNKNOWN = "unknown"


class SchemaType(str, Enum):
    INVOICE      = "invoice"
    SALES_REPORT = "sales_report"
    INVENTORY    = "inventory"
    HR_RECORDS   = "hr_records"
    STUDENT_DATA = "student_data"
    FINANCIAL    = "financial"
    GENERIC      = "generic"


class Suggestion(BaseModel):
    id: str
    title: str
    description: str
    action: str
    data: dict[str, Any] = {}
    approved: Optional[bool] = None


class ExecutionStep(BaseModel):
    timestamp: str
    agent: str
    message: str
    level: str = "info"


class DiffEntry(BaseModel):
    row: int
    column: str
    before: Any
    after: Any
    change_type: str  # modified | removed | added


class AgentState(BaseModel):
    session_id: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[FileType] = None

    raw_data: Optional[Any] = None
    extracted_data: Optional[list[dict]] = None
    cleaned_data: Optional[list[dict]] = None
    schema_type: Optional[SchemaType] = None
    column_mapping: dict[str, str] = {}

    diff_entries: list[DiffEntry] = []
    plan: list[str] = []
    suggestions: list[Suggestion] = []
    execution_steps: list[ExecutionStep] = []

    output_excel_path: Optional[str] = None
    user_message: Optional[str] = None
    error: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING

    # Phase 2
    pending_formulas: list[str] = []
    pending_charts: list[str] = []
    reflection_report: Optional[dict] = None

    # Phase 4
    user_preferences: dict = {}
    session_history: list[dict] = []
    memory_snippets: list[dict] = []
    memory_context: Optional[dict] = None

    gemini_context: list[dict] = []

    model_config = {"arbitrary_types_allowed": True}
