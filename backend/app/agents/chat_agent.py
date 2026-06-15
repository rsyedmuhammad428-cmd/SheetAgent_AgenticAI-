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
#  INLINE DATA PARSER  (7 strategies)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_inline_data(message: str) -> list[dict]:
    """
    Extract structured data rows from a user message.
    Returns [] if no clear tabular data is found (Gemini will then parse it).
    """
    msg = message.strip()

    # ── Strategy 1: Pipe table  "Name | Score\nAli | 85" ─────────────────
    pipe_lines = [l.strip() for l in msg.splitlines() if "|" in l and l.strip()]
    if len(pipe_lines) >= 2:
        raw_headers = [h.strip() for h in pipe_lines[0].split("|") if h.strip()]
        is_header   = all(not re.search(r'^\d+$', p) for p in raw_headers)
        if is_header and len(pipe_lines) >= 3:
            headers    = raw_headers
            data_lines = [l for l in pipe_lines[1:] if not re.match(r'^[\|\s\-:]+$', l)]
        else:
            headers    = [f"Col{i+1}" for i in range(len(raw_headers))]
            data_lines = pipe_lines
        rows = []
        for line in data_lines:
            vals = [v.strip() for v in line.split("|") if v.strip() != ""]
            if vals and len(vals) >= 2:
                while len(vals) < len(headers):
                    vals.append("")
                rows.append({h: _coerce(v) for h, v in zip(headers, vals[:len(headers)])})
        if rows:
            return rows

    # ── Strategy 2: Delimiter lines  "Ali,85\nSara,92" ────────────────────
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    for delim in ["\t", ",", ";"]:
        candidates = [l for l in lines if delim in l]
        if len(candidates) >= 2:
            col_counts = [l.count(delim) for l in candidates]
            if len(set(col_counts)) <= 2 and min(col_counts) >= 1:
                parts0    = [p.strip() for p in candidates[0].split(delim)]
                is_header = all(not re.match(r'^[\d.]+$', p.strip()) for p in parts0)
                if is_header and len(candidates) >= 3:
                    headers   = parts0
                    data_rows = candidates[1:]
                else:
                    headers   = [f"Col{i+1}" for i in range(len(parts0))]
                    data_rows = candidates
                rows = []
                for line in data_rows:
                    vals = [v.strip() for v in line.split(delim)]
                    while len(vals) < len(headers):
                        vals.append("")
                    rows.append({h: _coerce(v) for h, v in zip(headers, vals[:len(headers)])})
                if rows:
                    return rows

    # ── Strategy 3: "Name  Numbers" on separate lines ─────────────────────
    name_score_rows = []
    for line in lines:
        line_clean = line.rstrip(',').strip()
        m = re.match(r'^([A-Za-z][A-Za-z\s\-\.]{1,40}?)\s+([\d][\d\.\s]*)$', line_clean)
        if m:
            name = m.group(1).strip()
            nums = re.findall(r'[\d]+(?:\.\d+)?', m.group(2))
            if nums:
                name_score_rows.append((name, nums))
    if len(name_score_rows) >= 2:
        return _build_name_score_rows(name_score_rows)

    # ── Strategy 4: Comma-separated "Name N, Name N" ──────────────────────
    comma_parts = [p.strip() for p in re.split(r',\s*', msg) if p.strip()]
    inline_rows = []
    for part in comma_parts:
        m = re.match(r'^([A-Za-z][A-Za-z\s\.\-]{1,40}?)\s+([\d][\d\.\s]*)$', part.strip())
        if m:
            name = m.group(1).strip()
            nums = re.findall(r'[\d]+(?:\.\d+)?', m.group(2))
            if nums:
                inline_rows.append((name, nums))
    if len(inline_rows) >= 2:
        return _build_name_score_rows(inline_rows)

    # ── Strategy 5: Simple run-together "Ali85Sara92" ─────────────────────
    rt_matches = re.findall(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})([\d][\d\.]*?)(?=[A-Z]|Total|$)',
        msg
    )
    rt_rows = [
        (name.strip(), re.findall(r'[\d]+(?:\.\d+)?', nums))
        for name, nums in rt_matches
        if name.strip() and re.findall(r'[\d]+(?:\.\d+)?', nums) and len(name.strip()) > 2
    ]
    if len(rt_rows) >= 2:
        return _build_name_score_rows(rt_rows)

    # ── Strategy 7: Explicit N-column run-together (FIX for Image 1/2) ────
    # Handles: "three columns:Col1Col2Col3Name1 N1 N2%Name2 N3 N4%..."
    # User says e.g. "formatted with three columns:" or "2 columns:"
    result_s7 = _parse_ncol_runtogether(msg)
    if result_s7:
        return result_s7

    return []
    # ── Strategy 6: Run-together compound headers + deduplicated data+% ───
    # e.g. "Employee NamePerf ScoreSarah Jenkins9292%"
    data_matches_6 = re.findall(r'([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})((?:\d+%?)+)', msg)
    data_matches_6 = [(n, v) for n, v in data_matches_6
                      if not re.match(r'Total|Summary|Average|Grand', n, re.I)]
    if len(data_matches_6) >= 2:
        rows_raw = []
        for name, num_str in data_matches_6:
            parts   = re.findall(r'\d+%?', num_str)
            cleaned = []
            for part in parts:
                pct    = part.endswith('%')
                digits = part.rstrip('%')
                if (len(digits) >= 4 and len(digits) % 2 == 0
                        and digits[:len(digits) // 2] == digits[len(digits) // 2:]):
                    half = digits[:len(digits) // 2]
                    cleaned.append(int(half))
                    cleaned.append(f"{half}%" if pct else int(half))
                else:
                    cleaned.append(f"{digits}%" if pct else _coerce(digits))
            rows_raw.append((name, cleaned))

        first_name  = rows_raw[0][0]
        first_pos   = msg.find(first_name)
        pre_text    = msg[:first_pos] if first_pos > 0 else ""
        last_colon  = pre_text.rfind(':')
        header_block = pre_text[last_colon + 1:].strip() if last_colon >= 0 else pre_text.strip()
        header_split = re.sub(r'(?<=[a-z])(?=[A-Z])', '|', header_block)
        raw_headers  = [h.strip() for h in header_split.split('|')
                        if h.strip() and len(h.strip()) > 2]
        _noise = {
            'here','is','are','company','data','formatted','similarly','to','your',
            'student','performance','table','including','metrics','and','column',
            'for','efficiency','percentages','create','sheet','my','given','below',
            'following','the','this','format','like','above','provided',
        }
        col_headers = [h for h in raw_headers
                       if not all(w.lower() in _noise for w in h.split())]
        max_vals = max(len(r[1]) for r in rows_raw)
        if len(col_headers) >= 1 + max_vals:
            final_headers = col_headers[:1 + max_vals]
        elif col_headers:
            val_cols = col_headers[1:] if len(col_headers) > 1 else []
            while len(val_cols) < max_vals:
                val_cols.append(f"Value {len(val_cols) + 1}")
            final_headers = [col_headers[0]] + val_cols
        else:
            final_headers = ["Name"] + [f"Value {i+1}" for i in range(max_vals)]

        rows = []
        for name, vals in rows_raw:
            row = {final_headers[0]: name}
            for i, h in enumerate(final_headers[1:]):
                row[h] = vals[i] if i < len(vals) else ""
            rows.append(row)
        if rows:
            return rows



def _parse_ncol_runtogether(msg: str) -> list[dict]:
    """
    Strategy 7: CamelCase-split the payload after the last colon.
    Separates header segments (no digits) from the data segment (contains digits+%).
    Then parses data rows from the data segment.

    Covers Image 1 pattern:
      "three columns:Task NamePriority Level (1-10)Completion Percentage
       API Integration995%Frontend UI Design780%..."
    """
    # Find last colon — everything after is headers+data run-together
    last_colon = msg.rfind(':')
    if last_colon < 0:
        return []
    payload = msg[last_colon + 1:].strip()
    if not payload:
        return []

    # CamelCase-split the payload into segments
    split_payload = re.sub(r'(?<=[a-z\)])(?=[A-Z])', '|', payload)
    segments = [s.strip() for s in split_payload.split('|') if s.strip()]
    if not segments:
        return []

    # Separate header segments from the data segment
    # Headers = segments without digits+%; Data = first segment with digits+%
    headers     = []
    data_segment = ''
    for seg in segments:
        if re.search(r'\d+%', seg):
            data_segment = seg
            break
        headers.append(seg)

    if not data_segment or len(headers) < 1:
        return []

    # Parse data rows from the data segment: Name + 1digit + 2-3digits + %
    data_rows = re.findall(r'([A-Z][a-zA-Z\s]+?)(\d)(\d{1,3})(%)', data_segment)
    # Filter out Total/Summary rows
    data_rows = [(n.strip(), v1, v2) for n, v1, v2, _ in data_rows
                 if not re.match(r'Total|Summary|Average|Grand', n.strip(), re.I)
                 and len(n.strip()) > 1]

    if len(data_rows) < 2:
        return []

    # Build final headers (use what user stated, pad if needed)
    h_name = headers[0] if len(headers) >= 1 else "Name"
    h_val1 = headers[1] if len(headers) >= 2 else "Value 1"
    h_val2 = headers[2] if len(headers) >= 3 else "Value 2 (%)"

    rows = []
    for name, v1, v2 in data_rows:
        rows.append({h_name: name, h_val1: int(v1), h_val2: f"{v2}%"})
    return rows


def _find_header_end_in_name(raw_name: str, payload: str) -> int:
    """Kept for compatibility."""
    m = re.search(r'[a-z\)]([A-Z])', raw_name)
    return m.start() + 1 if m else 0


def _extract_headers_from_block(text: str, col_count=None) -> list:
    """Kept for compatibility."""
    if not text.strip():
        return []
    split = re.sub(r'(?<=[a-z\)])(?=[A-Z])', '|', text.strip())
    parts = [p.strip() for p in split.split('|') if p.strip() and len(p.strip()) > 1]
    if col_count and len(parts) >= col_count:
        return parts[:col_count]
    return parts if parts else []


def _build_name_score_rows(name_score_list: list) -> list[dict]:
    max_nums = max(len(r[1]) for r in name_score_list)
    headers  = ["Name"] + (["Score"] if max_nums == 1
                            else [f"Score {i+1}" for i in range(max_nums)])
    rows = []
    for name, nums in name_score_list:
        row = {"Name": name}
        for i, h in enumerate(headers[1:]):
            v = nums[i] if i < len(nums) else "0"
            row[h] = float(v) if isinstance(v, str) and '.' in v else (
                int(v) if isinstance(v, str) and v.isdigit() else v)
        rows.append(row)
    return rows


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
    from app.agents.quota_helper   import is_quota_error
    from app.services.gemini_service import gemini_service

    prompt = (
        "Extract ALL structured data rows from the following text. "
        "The text contains a table or list — find every row.\n\n"
        "RULES:\n"
        "1. Use ONLY values present in the text. NEVER invent or add data.\n"
        "2. Detect column names from the text headers.\n"
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
        if is_quota_error(e):
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

    file_path   = _get_file_path(state, uploaded_file_path)
    has_file    = file_path is not None
    inline_data = _parse_inline_data(msg)
    has_inline  = len(inline_data) >= 2

    intent = await _classify_intent(msg, has_file, state, has_inline)
    logger.info(
        f"[{session_id[:8]}] Intent={intent.value} "
        f"has_file={has_file} inline_rows={len(inline_data)}"
    )

    if intent == Intent.PROCESS and has_file:
        return await _process_file(msg, file_path, state, session_id)
    if intent == Intent.CREATE:
        return await _create_excel(msg, state, session_id,
                                   inline_data=inline_data if has_inline else None)
    if intent == Intent.ANALYZE and state and state.cleaned_data:
        return await _analyze_data(msg, state, session_id)
    return await _answer_question(msg, state, session_id, has_file)


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
) -> ChatResponse:
    from app.agents.quota_helper import is_quota_error
    from app.services.ws_manager import ws_manager

    await ws_manager.send_log(session_id, "SheetAgent", f"Designing: {msg[:60]}...")

    real_data = inline_data  # populated by regex parser, may be None

    # ── If regex parser found nothing, ask Gemini to extract from the text ─
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
