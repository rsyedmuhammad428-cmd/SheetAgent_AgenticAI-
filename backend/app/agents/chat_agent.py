"""
Chat Agent — Phase 5
Handles all user messages in the chat panel:

1. Slash commands  → /plan /clean /chart /approve /export
2. Excel instructions → "create invoice template", "make sales report with charts"
3. Analytics questions → "what is the average revenue?"
4. General questions → answered by Gemini with dataset context
5. File-based tasks → trigger pipeline on uploaded file
"""
import json
from pathlib import Path
from enum import Enum

from app.models.state import AgentState, AgentStatus
from app.services.gemini_service import gemini_service
from app.services.instruction_parser import parse_instruction_to_config
from app.services.instruction_excel_generator import generate_from_instruction
from app.services.memory_service import get_preferences
from app.services.ws_manager import ws_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MessageIntent(str, Enum):
    SLASH_COMMAND    = "slash_command"
    CREATE_EXCEL     = "create_excel"
    ANALYTICS        = "analytics"
    GENERAL_QUESTION = "general_question"
    UNKNOWN          = "unknown"


SLASH_COMMANDS = {
    "/plan":    "Generate an execution plan for the uploaded file",
    "/clean":   "Run data cleaning on the uploaded file",
    "/chart":   "Generate charts for the current dataset",
    "/approve": "Approve all pending suggestions",
    "/export":  "Export the current dataset to Excel",
    "/help":    "Show all available commands",
}

HELP_TEXT = """**Available commands:**
• `/plan` — Generate execution plan for uploaded file
• `/clean` — Run data cleaning
• `/chart` — Auto-generate charts
• `/approve` — Approve all suggestions
• `/export` — Export to Excel
• `/help` — Show this help

**Or just describe what you want:**
• *"Create an invoice template with item table and tax"*
• *"Make a monthly sales report with bar chart"*
• *"What is the average revenue?"*
• *"Show me the top 5 products"*"""


class ChatResponse:
    def __init__(self, text: str, intent: MessageIntent, action: dict | None = None):
        self.text = text
        self.intent = intent
        self.action = action or {}

    def to_dict(self):
        return {"text": self.text, "intent": self.intent.value, "action": self.action}


async def handle_message(
    message: str,
    state: AgentState | None,
    session_id: str,
) -> ChatResponse:
    """Route user message to the correct handler."""

    msg = message.strip()

    # ── Slash commands ────────────────────────────────────────────────────────
    if msg.startswith("/"):
        return await _handle_slash(msg, state, session_id)

    # ── Detect intent via Gemini ──────────────────────────────────────────────
    intent = await _detect_intent(msg, state)

    if intent == MessageIntent.CREATE_EXCEL:
        return await _handle_create_excel(msg, session_id)

    if intent == MessageIntent.ANALYTICS and state and state.cleaned_data:
        return await _handle_analytics(msg, state)

    return await _handle_general(msg, state)


# ── Slash command handler ──────────────────────────────────────────────────────

async def _handle_slash(msg: str, state: AgentState | None, session_id: str) -> ChatResponse:
    cmd = msg.split()[0].lower()

    if cmd == "/help":
        return ChatResponse(HELP_TEXT, MessageIntent.SLASH_COMMAND)

    if cmd == "/plan":
        if not state:
            return ChatResponse("Please upload a file first before generating a plan.", MessageIntent.SLASH_COMMAND)
        return ChatResponse(
            "Generating execution plan... check the Logs tab for live progress.",
            MessageIntent.SLASH_COMMAND,
            action={"trigger": "run_pipeline"},
        )

    if cmd == "/approve":
        return ChatResponse(
            "Approving all suggestions and generating Excel...",
            MessageIntent.SLASH_COMMAND,
            action={"trigger": "approve_all"},
        )

    if cmd == "/chart":
        if not state or not state.output_excel_path:
            return ChatResponse("Generate an Excel file first, then I can add charts.", MessageIntent.SLASH_COMMAND)
        return ChatResponse(
            "Generating charts for your dataset...",
            MessageIntent.SLASH_COMMAND,
            action={"trigger": "generate_charts"},
        )

    if cmd == "/export":
        if state and state.output_excel_path:
            filename = Path(state.output_excel_path).name
            return ChatResponse(
                f"Your Excel file is ready: **{filename}**",
                MessageIntent.SLASH_COMMAND,
                action={"trigger": "download", "filename": filename},
            )
        return ChatResponse("No Excel file generated yet. Upload data first.", MessageIntent.SLASH_COMMAND)

    if cmd == "/clean":
        return ChatResponse(
            "Running cleaning pipeline...",
            MessageIntent.SLASH_COMMAND,
            action={"trigger": "run_pipeline", "step": "clean"},
        )

    return ChatResponse(
        f"Unknown command: `{cmd}`\n\n{HELP_TEXT}",
        MessageIntent.SLASH_COMMAND,
    )


# ── Create Excel from instruction ─────────────────────────────────────────────

async def _handle_create_excel(instruction: str, session_id: str) -> ChatResponse:
    await ws_manager.send_log(session_id, "ChatAgent", f"Parsing instruction: '{instruction}'")

    try:
        prefs = await get_preferences()
        config = await parse_instruction_to_config(instruction, prefs)

        await ws_manager.send_log(
            session_id, "ChatAgent",
            f"Building '{config.title}' — {len(config.sheets)} sheet(s)..."
        )

        output_path = await generate_from_instruction(config, session_id)
        filename = output_path.name

        await ws_manager.broadcast(session_id, {
            "type": "excel_ready",
            "session_id": session_id,
            "data": {
                "filename": filename,
                "download_url": f"/api/download/excel/{filename}",
                "title": config.title,
                "sheets": [s.name for s in config.sheets],
                "has_charts": bool(config.charts),
            }
        })

        sheets_list = ", ".join(f"*{s.name}*" for s in config.sheets)
        charts_note = f" + {len(config.charts)} chart(s)" if config.charts else ""
        cond_note = f" + {len(config.conditional_rules)} formatting rule(s)" if config.conditional_rules else ""

        response_text = (
            f"✅ **{config.title}** is ready!\n\n"
            f"📋 Sheets: {sheets_list}{charts_note}{cond_note}\n\n"
            f"Click **Download** below to get your Excel file."
        )

        return ChatResponse(
            response_text,
            MessageIntent.CREATE_EXCEL,
            action={
                "trigger": "download",
                "filename": filename,
                "download_url": f"/api/download/excel/{filename}",
                "title": config.title,
            },
        )

    except Exception as e:
        logger.error("create_excel_error", error=str(e))
        return ChatResponse(
            f"Sorry, I couldn't generate that Excel file. Error: {e}",
            MessageIntent.CREATE_EXCEL,
        )


# ── Analytics handler ─────────────────────────────────────────────────────────

async def _handle_analytics(message: str, state: AgentState) -> ChatResponse:
    from app.agents.analytics_agent import run_analytics_agent
    result = await run_analytics_agent(state, message)
    return ChatResponse(result.answer, MessageIntent.ANALYTICS)


# ── General question handler ──────────────────────────────────────────────────

async def _handle_general(message: str, state: AgentState | None) -> ChatResponse:
    context = ""
    if state and state.cleaned_data:
        cols = list(state.cleaned_data[0].keys()) if state.cleaned_data else []
        context = (
            f"The user has a dataset loaded: {len(state.cleaned_data)} rows, "
            f"columns: {cols}, schema: {state.schema_type}"
        )

    prompt = f"""
You are SheetAgent AI, an intelligent Excel and data assistant.
{context}

User: "{message}"

Reply helpfully and concisely. If relevant, suggest actions the user can take
(e.g. upload a file, use /plan, describe what Excel they need).
Keep response under 100 words.
"""
    answer = await gemini_service.analyze(prompt)
    return ChatResponse(answer, MessageIntent.GENERAL_QUESTION)


# ── Intent detection ──────────────────────────────────────────────────────────

async def _detect_intent(message: str, state: AgentState | None) -> MessageIntent:
    """Quick Gemini call to classify the message intent."""
    has_data = bool(state and state.cleaned_data)

    prompt = f"""
Classify this user message into one of these intents:
- create_excel: user wants to CREATE a new Excel template/workbook from scratch based on description
- analytics: user is asking a question about data they've already uploaded
- general_question: everything else

User message: "{message}"
Has uploaded data: {has_data}

Reply with ONLY the intent string, nothing else.
"""
    try:
        raw = await gemini_service.analyze(prompt)
        intent_str = raw.strip().lower().replace('"', '').replace("'", "")
        return MessageIntent(intent_str)
    except Exception:
        return MessageIntent.GENERAL_QUESTION
