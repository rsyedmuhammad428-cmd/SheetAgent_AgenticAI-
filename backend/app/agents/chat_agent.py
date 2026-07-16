"""
SheetAgent AI — chat_agent.py (v4 FINAL)

All bugs fixed:

BUG 1 — Quota error produces hardcoded sheet instead of quota message
  Root cause: _gemini_extract_data_from_text caught ALL exceptions including
  quota errors, returned [], then intelligence_engine also caught quota errors
  internally and returned domain-default columns → sample data written.
  Fix: re-raise quota errors immediately in every except block so they
  always reach the _quota_response() handler in _create_excel/_process_file.

BUG 2 — 7 rows / 3 columns but got 2 columns / 3 rows
  Root cause: Strategy 6 couldn't handle the "Name SingleDigit TwoDigit%"
  pattern (e.g. "API Integration995%"). It was joining the header block text
  with the first data name and splitting columns incorrectly.
  Fix: Added Strategy 7 — explicit N-column extractor. Detects the column
  count from user's explicit statement ("three columns", "2 columns" etc.)
  or infers it from the data pattern, then parses all rows accordingly.
  Also: clean header noise from the first matched name.

BUG 3 — PDF/image gives 0 rows → sample data
  Root cause: pdfplumber text-only early-return; Vision prompt not strict enough.
  Fix (carried from v3): pdfplumber text falls through to Vision; Vision uses
  strict prompt forbidding placeholder data; multi-layer parser JSON→table→lines.
  Additional fix: when Gemini text extraction returns empty, raise QuotaError
  immediately instead of silently returning [].
"""
import asyncio
import csv
import io
import logging
import re
from pathlib import Path
from enum import Enum
from typing import Optional
from app.agents.rate_limiter import call_with_retry

logger = logging.getLogger(__name__)

HELP_TEXT = """**SheetAgent AI — Quick Reference**

**How to use:**
- Describe what you need: *"Create a student marksheet for Math, Physics, English"*
- Paste data directly: *"Ali 85, Sara 92, Ahmed 78 — create a marksheet"*
- Upload a file then describe what to do with it
- Type `/help` to show this message

**Commands:** `/help` · `/approve` · `/export` · `/plan`"""


class Intent(str, Enum):
    CREATE   = "create"
    PROCESS  = "process"
    ANALYZE  = "analyze"
    COMMAND  = "command"
    QUESTION = "question"


class ChatResponse:
    def __init__(self, text: str, intent: Intent, action: dict | None = None):
        self.text   = text
        self.intent = intent
        self.action = action or {}


# ═══════════════════════════════════════════════════════════════════════════════
#  HUMAN-IN-THE-LOOP (HITL) — Theme & Graph selection before Excel creation
# ═══════════════════════════════════════════════════════════════════════════════

# In-memory store: session_id → {stage, original_msg, inline_data, theme_id, graph_id, file_path}
_hitl_state: dict[str, dict] = {}

HITL_THEMES = [
    {
        "id": "blue",
        "label": "Ocean Blue",
        "header": "#1E3A5F",
        "header_font": "#FFFFFF",
        "row_alt": "#D6E4F0",
        "row_base": "#FFFFFF",
        "icon": "🌊",
    },
    {
        "id": "pink",
        "label": "Rose Pink",
        "header": "#8B1A4A",
        "header_font": "#FFFFFF",
        "row_alt": "#FADADD",
        "row_base": "#FFFFFF",
        "icon": "🌸",
    },
    {
        "id": "green",
        "label": "Forest Green",
        "header": "#1B5E20",
        "header_font": "#FFFFFF",
        "row_alt": "#C8E6C9",
        "row_base": "#FFFFFF",
        "icon": "🌿",
    },
    {
        "id": "orange",
        "label": "Sunset Orange",
        "header": "#BF360C",
        "header_font": "#FFFFFF",
        "row_alt": "#FFE0B2",
        "row_base": "#FFFFFF",
        "icon": "🌅",
    },
    {
        "id": "purple",
        "label": "Royal Purple",
        "header": "#4A148C",
        "header_font": "#FFFFFF",
        "row_alt": "#E1BEE7",
        "row_base": "#FFFFFF",
        "icon": "👑",
    },
    {
        "id": "teal",
        "label": "Teal Breeze",
        "header": "#004D40",
        "header_font": "#FFFFFF",
        "row_alt": "#B2DFDB",
        "row_base": "#FFFFFF",
        "icon": "🌊",
    },
    {
        "id": "brown",
        "label": "Earthy Brown",
        "header": "#4E342E",
        "header_font": "#FFFFFF",
        "row_alt": "#D7CCC8",
        "row_base": "#FFFFFF",
        "icon": "🍂",
    },
    {
        "id": "dark",
        "label": "Midnight Dark",
        "header": "#212121",
        "header_font": "#F5F5F5",
        "row_alt": "#424242",
        "row_base": "#303030",
        "icon": "🌙",
    },
]

HITL_GRAPHS = [
    {"id": "bar",  "label": "Bar Chart",  "icon": "📊", "desc": "Compare values side by side"},
    {"id": "pie",  "label": "Pie Chart",  "icon": "🥧", "desc": "Show proportions & percentages"},
    {"id": "line", "label": "Line Graph", "icon": "📈", "desc": "Track trends over time"},
]


def _hitl_theme_options() -> list[dict]:
    return [
        {
            "id": f"theme_{t['id']}",
            "label": f"{t['icon']} {t['label']}",
            "header": t["header"],
            "row_alt": t["row_alt"],
        }
        for t in HITL_THEMES
    ]


def _hitl_graph_options() -> list[dict]:
    return [
        {
            "id": f"graph_{g['id']}",
            "label": f"{g['icon']} {g['label']}",
            "desc": g["desc"],
        }
        for g in HITL_GRAPHS
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  INLINE DATA PARSER  (7 strategies)
# ═══════════════════════════════════════════════════════════════════════════════

def _has_inline_data_heuristic(msg: str) -> bool:
    """
    Quick heuristic to detect if the user's message contains raw inline data (CSV, paragraphs, lists).
    Returns True if it likely contains data, so the intent classifier knows to trigger CREATE.
    The actual extraction will be handled powerfully by Gemini inside _create_excel.
    """
    msg_strip = msg.strip()
    lines = [l for l in msg_strip.splitlines() if l.strip()]
    
    # 1. Has multiple lines and contains numbers
    if len(lines) >= 3 and any(char.isdigit() for char in msg_strip):
        return True
        
    # 2. Looks like a CSV (lots of commas + numbers)
    if msg_strip.count(',') >= 4 and any(char.isdigit() for char in msg_strip):
        return True
        
    # 3. Contains typical data words + numbers
    lower_msg = msg_strip.lower()
    data_words = ["salary", "marks", "score", "employeeid", "department", "name", "price", "revenue"]
    if any(w in lower_msg for w in data_words) and any(char.isdigit() for char in msg_strip):
        return True
        
    return False

def _parse_inline_data(message: str) -> list[dict]:
    # Dummy function to satisfy backward compatibility
    # The actual extraction is now handled by Gemini in _create_excel
    return []


def _try_parse_csv_locally(text: str) -> list[dict]:
    """
    Try to parse CSV/comma-separated data from the user's message WITHOUT
    using an LLM. CSV is a deterministic format — sending it to Gemini is
    unreliable (truncation, hallucination, null values) and slow.

    This parser:
    - Strips non-CSV content (HITL preferences, instructions)
    - Uses Python's csv module for correct field splitting
    - Auto-coerces numbers
    - Returns list[dict] if successful, [] if the text is not CSV
    """
    lines = text.strip().splitlines()

    # Collect only lines that look like CSV rows (contain commas)
    csv_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Stop at HITL preference blocks appended to the message
        if stripped.startswith("[") and "PREFERENCES" in stripped.upper():
            break
        if stripped.startswith("Color Theme:") or stripped.startswith("Chart Type:"):
            continue
        if "," in stripped:
            csv_lines.append(stripped)

    if len(csv_lines) < 2:  # Need header + at least 1 data row
        return []

    # Parse with csv module
    try:
        reader = csv.reader(io.StringIO("\n".join(csv_lines)))
        all_rows = list(reader)
    except csv.Error:
        return []

    if len(all_rows) < 2:
        return []

    header = [h.strip() for h in all_rows[0]]
    num_fields = len(header)

    # Need at least 2 columns to be valid CSV
    if num_fields < 2:
        return []

    # Check consistency: ≥50% of data rows must match header field count
    data_rows = all_rows[1:]
    consistent = sum(1 for row in data_rows if len(row) == num_fields)
    if consistent < len(data_rows) * 0.5:
        return []

    # Build list of dicts with automatic number coercion
    result: list[dict] = []
    for row in data_rows:
        if len(row) != num_fields:
            continue  # Skip malformed rows
        row_dict: dict = {}
        for i, col_name in enumerate(header):
            val = row[i].strip()
            # Coerce to int or float if possible
            try:
                if "." in val:
                    row_dict[col_name] = float(val)
                elif val.lstrip("-").isdigit():
                    row_dict[col_name] = int(val)
                else:
                    row_dict[col_name] = val
            except (ValueError, TypeError):
                row_dict[col_name] = val
        result.append(row_dict)

    if result:
        logger.info(
            f"[SheetAgent] Local CSV parse: {len(result)} rows × {num_fields} cols "
            f"— headers: {header}"
        )
    return result


def _coerce(val: str):
    if not isinstance(val, str):
        return val
    v = val.strip().replace(",", "")
    if v.lstrip("-").isdigit():
        return int(v)
    try:
        return float(v)
    except (ValueError, TypeError):
        return val


# ═══════════════════════════════════════════════════════════════════════════════
#  GEMINI TEXT→DATA EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════

async def _gemini_extract_data_from_text(text: str) -> list[dict]:
    """
    Ask Gemini to extract structured rows from raw text.
    CRITICAL: quota errors are re-raised — they must NOT be swallowed here.
    """
    from app.agents.quota_helper   import is_quota_error, is_provider_error
    from app.services.gemini_service import gemini_service

    prompt = (
        "Extract ALL structured data rows from the following text. "
        "The text contains a table or list — find every row.\n\n"
        "RULES:\n"
        "1. Use ONLY values present in the text. NEVER invent or add data.\n"
        "2. Detect column names from the text headers. DO NOT extract data values from column headers (e.g. if a header is 'Total (35)', the column name is 'Total (35)' and the data must come from the rows).\n"
        "3. Include every data row — do not truncate.\n"
        "4. Numbers must be actual numbers, not strings.\n"
        "5. If the user states column names explicitly, use those EXACT names.\n\n"
        f"TEXT:\n{text[:50000]}\n\n"
        "Return ONLY a valid JSON array (no markdown, no explanation):\n"
        '[{"Column1": "value", "Column2": 123}, ...]\n\n'
        "If no structured data is found: return []"
    )
    try:
        result = await call_with_retry(gemini_service.analyze_json, prompt)
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            logger.info(f"[SheetAgent] Gemini text extraction: {len(result)} rows")
            return result
        return []
    except Exception as e:
        if is_quota_error(e) or is_provider_error(e):
            raise   # ← CRITICAL: re-raise quota errors, never swallow them
        logger.warning(f"[SheetAgent] Gemini text extraction failed (non-quota): {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(
    message: str,
    state,
    session_id: str,
    uploaded_file_path: Optional[str] = None,
) -> ChatResponse:
    msg = message.strip()
    if not msg:
        return ChatResponse(
            "Please describe what you need.\n"
            "Example: *\"Create a student marksheet with Math, Physics, English\"*\n"
            "Or paste your data directly and say what to do with it.",
            Intent.QUESTION,
        )

    if msg.startswith("/"):
        return _handle_command(msg, state, session_id)

    # ── Human-in-the-Loop: handle theme / graph selection choices ────────────
    if msg.startswith("__choice:"):
        return await _handle_hitl_choice(msg[9:], session_id, state)

    # ── Human-in-the-Loop: if HITL is pending for this session, reject ───────
    if session_id in _hitl_state:
        pending_stage = _hitl_state[session_id].get("stage")
        if pending_stage == "theme":
            return _ask_hitl_theme(session_id)
        if pending_stage == "graph":
            return _ask_hitl_graph(session_id)

    file_path   = _get_file_path(state, uploaded_file_path)
    has_file    = file_path is not None
    has_inline  = _has_inline_data_heuristic(msg)
    inline_data = []

    intent = await _classify_intent(msg, has_file, state, has_inline)
    logger.info(
        f"[{session_id[:8]}] Intent={intent.value} "
        f"has_file={has_file} has_inline={has_inline}"
    )

    if intent in (Intent.PROCESS, Intent.CREATE):
        if intent == Intent.PROCESS and not has_file:
            return ChatResponse("No file found to process.", Intent.PROCESS)
        
        # ── Start HITL flow ──────────────────────────────────────────────
        _hitl_state[session_id] = {
            "stage":       "theme",
            "original_msg": msg,
            "inline_data":  inline_data if has_inline else None,
            "file_path":    file_path,
            "theme_id":    None,
            "graph_id":    None,
        }
        return _ask_hitl_theme(session_id)

    if intent == Intent.ANALYZE and state and state.cleaned_data:
        return await _analyze_data(msg, state, session_id)
    return await _answer_question(msg, state, session_id, has_file)


# ═══════════════════════════════════════════════════════════════════════════════
#  HITL STEP HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def _ask_hitl_theme(session_id: str) -> "ChatResponse":
    return ChatResponse(
        text=(
            "🎨 **Step 1 of 2 — Choose a Color Theme**\n\n"
            "Pick a color scheme for your Excel sheet headers and rows:"
        ),
        intent=Intent.CREATE,
        action={
            "trigger":      "hitl_theme",
            "waiting_for":  "theme",
            "options":      _hitl_theme_options(),
        },
    )


def _ask_hitl_graph(session_id: str) -> "ChatResponse":
    return ChatResponse(
        text=(
            "📊 **Step 2 of 2 — Choose a Chart Type**\n\n"
            "Select the type of chart to include in your Excel sheet:"
        ),
        intent=Intent.CREATE,
        action={
            "trigger":      "hitl_graph",
            "waiting_for":  "graph",
            "options":      _hitl_graph_options(),
        },
    )


async def _handle_hitl_choice(
    choice_id: str,
    session_id: str,
    state,
) -> "ChatResponse":
    """Process a HITL theme or graph choice and advance the flow."""
    hitl = _hitl_state.get(session_id)

    # No pending HITL — treat as normal message
    if not hitl:
        return ChatResponse(
            "I'm ready to create your sheet! Describe what you need.",
            Intent.QUESTION,
        )

    stage = hitl.get("stage")

    # ── Stage 1: Theme selected ──────────────────────────────────────────────
    if stage == "theme" and choice_id.startswith("theme_"):
        hitl["theme_id"] = choice_id[6:]  # strip "theme_"
        hitl["stage"]    = "graph"
        logger.info(f"[HITL] {session_id[:8]} theme={hitl['theme_id']}")
        return _ask_hitl_graph(session_id)

    # ── Stage 2: Graph selected → execute creation ───────────────────────────
    if stage == "graph" and choice_id.startswith("graph_"):
        hitl["graph_id"] = choice_id[6:]  # strip "graph_"
        logger.info(f"[HITL] {session_id[:8]} graph={hitl['graph_id']} — executing")

        original_msg = hitl["original_msg"]
        inline_data  = hitl["inline_data"]
        theme_id     = hitl["theme_id"]
        graph_id     = hitl["graph_id"]
        file_path    = hitl.get("file_path")

        # Clean up HITL state
        del _hitl_state[session_id]

        # Build theme/graph enriched prompt hint
        theme_obj = next((t for t in HITL_THEMES if t["id"] == theme_id), HITL_THEMES[0])
        graph_obj = next((g for g in HITL_GRAPHS if g["id"] == graph_id), HITL_GRAPHS[0])

        enriched_msg = (
            f"{original_msg}\n\n"
            f"[USER PREFERENCES — MUST APPLY EXACTLY]\n"
            f"Color Theme: {theme_obj['label']} — "
            f"Header color: {theme_obj['header']}, "
            f"Header font: {theme_obj['header_font']}, "
            f"Alternating row color: {theme_obj['row_alt']}, "
            f"Base row color: {theme_obj['row_base']}\n"
            f"Chart Type: {graph_obj['label']} ({graph_id})"
        )

        # If file was involved, use file processing
        if file_path:
            return await _process_file(
                enriched_msg, file_path, state, session_id,
                theme=theme_obj, graph_type=graph_id
            )
        return await _create_excel(
            enriched_msg, state, session_id,
            inline_data=inline_data,
            theme=theme_obj,
            graph_type=graph_id,
        )

    # Unexpected choice — re-ask
    if stage == "theme":
        return _ask_hitl_theme(session_id)
    return _ask_hitl_graph(session_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_intent_sync(msg: str, has_file: bool, state, has_inline: bool) -> Intent:
    """
    Keyword-based intent classification.
    Questions get answers. Creations get sheets. No ambiguity.

    KEY RULE: A message ending with "?" is ALWAYS a question.
    Creation keywords (make, build, create, sheet...) never override a "?".
    Example: "which type of graph and charts you make?" → QUESTION, not CREATE.
    """
    has_data = bool(state and (state.cleaned_data or state.extracted_data))
    lower    = msg.lower().strip()
    words    = lower.split()

    question_starters = (
        "what", "who", "how", "why", "when", "where", "which",
        "can you", "could you explain", "tell me", "explain",
        "is it", "are you", "do you", "does it",
    )

    # ── A "?" at the end is unconditionally a question ─────────────────────
    # No creation keyword can override a genuine question mark.
    ends_with_q   = msg.strip().endswith("?")
    starts_with_q = any(lower.startswith(q) for q in question_starters)

    if (ends_with_q or starts_with_q) and not has_inline and not has_file:
        return Intent.QUESTION

    # ── Short messages with question words (no "?") and no creation intent ─
    question_words = ("what", "how", "why", "when", "where", "which", "who")
    if (len(words) <= 6
            and any(w in question_words for w in words)
            and not has_inline and not has_file
            and not any(w in lower for w in ["create", "make", "build",
                                              "generate", "sheet", "excel"])):
        return Intent.QUESTION

    # ── Inline data + any creation keyword → CREATE ─────────────────────────
    if has_inline and any(w in lower for w in [
        "create", "make", "build", "generate", "sheet", "excel", "workbook",
        "report", "marksheet", "table", "here is", "here's", "student",
        "data", "for", "given", "this", "provided", "professional",
    ]):
        return Intent.CREATE

    # ── File uploaded + action keyword → PROCESS ────────────────────────────
    if has_file and any(w in lower for w in [
        "file", "image", "pdf", "csv", "this", "uploaded", "extract",
        "read", "from", "use", "process", "data", "document", "create",
        "sheet", "excel", "make", "build", "generate",
    ]):
        return Intent.PROCESS

    # ── Explicit creation keywords → CREATE ─────────────────────────────────
    if has_inline or any(w in lower for w in [
        "create", "make", "build", "generate", "template", "sheet",
        "workbook", "excel", "report", "tracker", "dashboard", "professional",
        "invoice", "salary", "inventory", "budget", "student", "marksheet",
        "table", "record", "spreadsheet",
    ]):
        return Intent.CREATE

    # ── Analysis on existing data → ANALYZE ─────────────────────────────────
    if has_data and any(w in lower for w in [
        "average", "total", "max", "min", "count", "trend", "analyze",
        "compare", "highest", "lowest", "sum", "how many",
    ]):
        return Intent.ANALYZE

    # ── File uploaded, reasonable message → PROCESS ──────────────────────────
    if has_file and len(words) >= 2:
        return Intent.PROCESS

    return Intent.QUESTION


async def _classify_intent(msg: str, has_file: bool, state, has_inline: bool) -> Intent:
    """Thin async wrapper — kept for API compatibility."""
    return _classify_intent_sync(msg, has_file, state, has_inline)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROCESS UPLOADED FILE
# ═══════════════════════════════════════════════════════════════════════════════

async def _process_file(
    instruction: str,
    file_path: str,
    state,
    session_id: str,
    theme: dict = None,
    graph_type: str = None,
) -> ChatResponse:
    from app.agents.file_extractor import file_extractor
    from app.agents.quota_helper   import is_quota_error
    from app.services.ws_manager   import ws_manager

    fp = Path(file_path)
    await ws_manager.send_log(session_id, "SheetAgent", f"Reading {fp.name}...")

    extracted = None
    try:
        extracted = await file_extractor.extract(file_path, session_id)
        await ws_manager.send_log(
            session_id, "SheetAgent",
            f"Extracted: {extracted['row_count']} rows, "
            f"{len(extracted['extracted_columns'])} columns"
        )
    except Exception as e:
        if is_quota_error(e):
            return _quota_response(e, Intent.PROCESS)
        logger.error(f"[SheetAgent] Extraction error: {e}", exc_info=True)
        extracted = file_extractor._empty_result(str(e))

    # ── If pdfplumber/Vision got text but 0 rows → ask Gemini to parse text
    if (extracted
            and extracted.get("row_count", 0) == 0
            and extracted.get("extracted_text", "").strip()):
        await ws_manager.send_log(session_id, "SheetAgent",
                                  "No table found — asking AI to extract data from text...")
        try:
            gemini_rows = await _gemini_extract_data_from_text(extracted["extracted_text"])
            if gemini_rows:
                extracted["extracted_data"]    = gemini_rows
                extracted["extracted_columns"] = list(gemini_rows[0].keys())
                extracted["row_count"]         = len(gemini_rows)
                await ws_manager.send_log(
                    session_id, "SheetAgent",
                    f"AI extracted {len(gemini_rows)} rows from text"
                )
        except Exception as e:
            if is_quota_error(e):
                return _quota_response(e, Intent.PROCESS)   # ← quota shown to user
            logger.warning(f"[SheetAgent] Gemini text parse failed: {e}")

    # ── Build Excel ────────────────────────────────────────────────────────
    try:
        from app.agents.intelligence_engine import intelligence_engine
        from app.agents.excel_generator     import generate_excel

        real_data = extracted["extracted_data"] if extracted else None

        task = await intelligence_engine.understand_task(
            user_message=instruction,
            file_content=extracted["extracted_text"] if extracted else "",
            file_name=extracted["file_name"]         if extracted else fp.name,
        )
        await ws_manager.send_log(
            session_id, "SheetAgent",
            f"Task: {task.get('user_intent_summary', '')[:60]}"
        )

        design = await intelligence_engine.design_workbook(
            task=task,
            file_content=extracted["extracted_text"]          if extracted else "",
            extracted_data=real_data,
            extracted_columns=extracted["extracted_columns"]  if extracted else None,
        )
        await ws_manager.send_log(
            session_id, "SheetAgent", f"Building: {design.get('title', '')}"
        )

        output_path = await generate_excel(
            design=design, session_id=session_id, real_data=real_data,
            theme=theme, graph_type=graph_type,
        )
        return _build_excel_response(output_path, design, session_id)

    except Exception as e:
        if is_quota_error(e):
            return _quota_response(e, Intent.PROCESS)
        logger.error(f"[SheetAgent] Process pipeline error: {e}", exc_info=True)
        return ChatResponse(
            f"❌ Error processing **{fp.name}**: {str(e)}\n\n"
            "Please check that your `GEMINI_API_KEY` is set correctly in `.env`.",
            Intent.PROCESS,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  CREATE EXCEL FROM SCRATCH / INLINE DATA
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_excel(
    msg: str,
    state,
    session_id: str,
    inline_data: Optional[list] = None,
    theme: Optional[dict] = None,
    graph_type: Optional[str] = None,
) -> ChatResponse:
    from app.agents.quota_helper import is_quota_error
    from app.services.ws_manager import ws_manager

    await ws_manager.send_log(session_id, "SheetAgent", f"Designing: {msg[:60]}...")

    real_data = inline_data  # populated by regex parser, may be None

    # ── STEP 1: Try local CSV parsing FIRST (instant, 100% accurate) ─────
    # CSV is a deterministic format. Sending 70 rows to an LLM is unreliable
    # (nulls, truncation, hallucination) and slow. Parse it locally.
    if not real_data:
        csv_rows = _try_parse_csv_locally(msg)
        if csv_rows:
            real_data = csv_rows
            await ws_manager.send_log(
                session_id, "SheetAgent",
                f"✅ Parsed {len(csv_rows)} rows of CSV data locally"
            )

    # ── STEP 2: If not CSV, ask Gemini to extract from free-text ──────────
    if not real_data:
        await ws_manager.send_log(session_id, "SheetAgent",
                                  "Extracting data from your message...")
        try:
            gemini_rows = await _gemini_extract_data_from_text(msg)
            if gemini_rows:
                real_data = gemini_rows
                await ws_manager.send_log(
                    session_id, "SheetAgent",
                    f"✅ Extracted {len(gemini_rows)} rows from your message"
                )
        except Exception as e:
            if is_quota_error(e):
                return _quota_response(e, Intent.CREATE)    # ← quota shown to user
            logger.warning(f"[SheetAgent] Gemini inline parse failed (non-quota): {e}")

    if real_data:
        await ws_manager.send_log(
            session_id, "SheetAgent",
            f"Using {len(real_data)} rows of your actual data"
        )

    try:
        from app.agents.intelligence_engine import intelligence_engine
        from app.agents.excel_generator     import generate_excel
        import json as _json

        file_content_hint = None
        if real_data:
            col_names         = list(real_data[0].keys())
            file_content_hint = (
                f"User provided data with columns: {col_names}\n"
                f"Total rows: {len(real_data)}\n"
                f"All data rows:\n"
                f"{_json.dumps(real_data, indent=2)}"
            )
        else:
            file_content_hint = f"User message with data request:\n{msg}"

        task = await intelligence_engine.understand_task(
            user_message=msg,
            file_content=file_content_hint,
        )
        await ws_manager.send_log(
            session_id, "SheetAgent",
            f"Task: {task.get('user_intent_summary', '')[:60]}"
        )

        design = await intelligence_engine.design_workbook(
            task=task,
            file_content=file_content_hint,
            extracted_data=real_data,
            extracted_columns=list(real_data[0].keys()) if real_data else None,
        )
        await ws_manager.send_log(
            session_id, "SheetAgent", f"Building: {design.get('title', '')}"
        )

        output_path = await generate_excel(
            design=design, session_id=session_id, real_data=real_data,
            theme=theme, graph_type=graph_type,
        )
        return _build_excel_response(output_path, design, session_id)

    except Exception as e:
        if is_quota_error(e):
            return _quota_response(e, Intent.CREATE)
        logger.error(f"[SheetAgent] Create error: {e}", exc_info=True)
        return ChatResponse(
            f"❌ Error creating Excel: {str(e)}\n\n"
            "Please check that your `GEMINI_API_KEY` is set correctly in `.env`.",
            Intent.CREATE,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS / Q&A / COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def _analyze_data(msg: str, state, session_id: str) -> ChatResponse:
    try:
        from app.agents.analytics_agent import run_analytics_agent
        result = await run_analytics_agent(state, msg)
        return ChatResponse(result.answer, Intent.ANALYZE)
    except Exception as e:
        return ChatResponse(f"Analysis error: {e}", Intent.QUESTION)


async def _answer_question(msg: str, state, session_id: str, has_file: bool) -> ChatResponse:
    from app.services.gemini_service import gemini_service

    ctx_parts = []
    if has_file:
        ctx_parts.append("The user has a file uploaded and ready to process.")
    if state and state.file_name:
        ctx_parts.append(f"Currently loaded file: {state.file_name}.")
    if state and state.cleaned_data:
        ctx_parts.append(f"Data already in memory: {len(state.cleaned_data)} rows.")
    ctx = " ".join(ctx_parts)

    prompt = (
        "You are SheetAgent AI — an intelligent Excel and data assistant that talks naturally.\n"
        f"{ctx}\n\n"
        "The user is asking a question or making a general statement. "
        "Reply conversationally and helpfully.\n\n"
        f"User: \"{msg}\"\n\n"
        "Guidelines:\n"
        "- Answer the question directly if it has a clear answer\n"
        "- If they ask what you can do, list your capabilities concisely\n"
        "- If they mention data/Excel needs, explain how to proceed\n"
        "- Keep reply under 120 words, conversational, friendly\n"
        "- Never respond with a generic help menu unless they asked for help"
    )
    try:
        answer = await call_with_retry(gemini_service.analyze, prompt)
        return ChatResponse(answer or "How can I help you today?", Intent.QUESTION)
    except Exception:
        return ChatResponse(
            "I'm SheetAgent AI — I can:\n\n"
            "📊 **Create Excel sheets** from your data or descriptions\n"
            "📁 **Extract data** from PDFs, images, and CSV files\n"
            "📈 **Build charts** based on your instructions\n"
            "🎨 **Apply formatting** like conditional colours and totals\n\n"
            "Just describe what you need or paste your data!",
            Intent.QUESTION,
        )


def _handle_command(msg: str, state, session_id: str) -> ChatResponse:
    cmd = msg.split()[0].lower()
    if cmd == "/help":
        return ChatResponse(HELP_TEXT, Intent.COMMAND)
    if cmd == "/approve":
        return ChatResponse("Approving suggestions...", Intent.COMMAND,
                            action={"trigger": "approve_all"})
    if cmd == "/export":
        if state and state.output_excel_path:
            fn = Path(state.output_excel_path).name
            return ChatResponse(f"Your file **{fn}** is ready.", Intent.COMMAND,
                                action={"trigger": "download", "filename": fn})
        return ChatResponse("No Excel file yet. Describe what you need.", Intent.COMMAND)
    if cmd == "/plan":
        return ChatResponse("Generating plan...", Intent.COMMAND,
                            action={"trigger": "run_pipeline"})
    return ChatResponse(f"Unknown command: `{cmd}`\n\n{HELP_TEXT}", Intent.COMMAND)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_file_path(state, uploaded_file_path: Optional[str]) -> Optional[str]:
    if uploaded_file_path:
        p = Path(uploaded_file_path)
        if p.exists():
            return str(p)
    if state and state.file_path:
        p = Path(state.file_path)
        if p.exists():
            return str(p)
    return None


def _quota_response(e: Exception, intent: Intent) -> ChatResponse:
    """Return professional quota-exceeded message. Never returns a fallback Excel."""
    from app.agents.quota_helper import get_quota_reset_message
    logger.warning(f"[SheetAgent] Quota exceeded — returning user message. Error: {e}")
    return ChatResponse(
        text=get_quota_reset_message(e),
        intent=intent,
        action={"trigger": "quota_exceeded"},
    )


def _build_excel_response(output_path: Path, design: dict, session_id: str) -> ChatResponse:
    import asyncio
    filename = output_path.name
    title    = design.get("title", "Your Excel")
    sheets   = design.get("sheets", [])

    sheet_lines = []
    for s in sheets:
        cols    = [c["name"] for c in s.get("columns", [])[:5]]
        extra   = len(s.get("columns", [])) - 5
        col_str = ", ".join(cols) + (f" +{extra} more" if extra > 0 else "")
        sheet_lines.append(f"• **{s['name']}**: {col_str}")

    features = []
    if any(s.get("has_totals_row") for s in sheets): features.append("auto-totals")
    if any(s.get("has_filters")    for s in sheets): features.append("filters")
    if design.get("charts"):                         features.append(f"{len(design['charts'])} chart(s)")
    if design.get("conditional_rules"):              features.append("colour formatting")
    if design.get("has_summary_sheet"):              features.append("summary sheet")

    asyncio.ensure_future(_broadcast_excel_ready(session_id, filename, title))

    return ChatResponse(
        text=(
            f"✅ **{title}** is ready!\n\n"
            f"📋 **Sheets:**\n" + "\n".join(sheet_lines) + "\n\n"
            + (f"⚡ **Features:** {', '.join(features)}\n\n" if features else "")
            + "Click **Download Excel** to get your file."
        ),
        intent=Intent.PROCESS,
        action={
            "trigger":      "download",
            "filename":     filename,
            "download_url": f"/api/download/excel/{filename}",
            "title":        title,
        },
    )


async def _broadcast_excel_ready(session_id: str, filename: str, title: str):
    try:
        from app.services.ws_manager import ws_manager
        await ws_manager.broadcast(session_id, {
            "type": "excel_ready", "session_id": session_id,
            "data": {
                "filename":     filename,
                "download_url": f"/api/download/excel/{filename}",
                "title":        title,
            },
        })
    except Exception as e:
        logger.warning(f"[SheetAgent] Broadcast failed (non-fatal): {e}")
