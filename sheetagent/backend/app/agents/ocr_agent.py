"""
OCR Agent — Phase 3
Full pipeline:
  input file
    ├── PDF (searchable) → pypdf/pdfplumber → structured tables
    ├── PDF (scanned)    → pdf2image → preprocess → img2table/EasyOCR
    └── Image            → preprocess → img2table/EasyOCR

After raw OCR, Gemini cleans and structures the extracted text.
"""
from pathlib import Path
import json
import shutil

from app.models.state import AgentState, AgentStatus, FileType
from app.parsers.image_preprocessor import preprocess_for_ocr, pdf_to_images, crop_to_content
from app.parsers.table_detector import detect_tables_img2table
from app.parsers.ocr_engine import ocr_engine, OCRTable
from app.parsers.pdf_parser import (
    is_searchable_pdf, extract_tables_from_searchable_pdf,
    extract_text_from_searchable_pdf, get_pdf_page_count
)
from app.services.gemini_service import gemini_service
from app.services.workspace_service import workspace_service
from app.services.ws_manager import ws_manager
import logging

logger = logging.getLogger(__name__)

MAX_PAGES_FREE = 10  # Gemini free tier rate limit protection


async def run_ocr_agent(state: AgentState) -> AgentState:
    """Entry point — routes to correct sub-pipeline based on file type."""
    await ws_manager.send_log(state.session_id, "OCRAgent", f"Starting OCR pipeline for: {state.file_name}")

    try:
        file_path = Path(state.file_path)

        if state.file_type == FileType.PDF:
            state = await _process_pdf(state, file_path)
        elif state.file_type == FileType.IMAGE:
            state = await _process_image(state, file_path)
        else:
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                f"File type {state.file_type} doesn't need OCR — skipping",
                level="warning"
            )

        return state

    except Exception as e:
        logger.error(f"OCRAgent error: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        await ws_manager.send_log(state.session_id, "OCRAgent", f"OCR failed: {e}", level="error")
        return state


# ── PDF pipeline ─────────────────────────────────────────────────────────────

async def _process_pdf(state: AgentState, pdf_path: Path) -> AgentState:
    searchable, char_count = is_searchable_pdf(pdf_path)
    page_count = get_pdf_page_count(pdf_path)

    await ws_manager.send_log(
        state.session_id, "OCRAgent",
        f"PDF: {page_count} pages, {'searchable' if searchable else 'scanned'} ({char_count} chars extracted)"
    )

    if searchable:
        return await _process_searchable_pdf(state, pdf_path)
    else:
        return await _process_scanned_pdf(state, pdf_path, page_count)


async def _process_searchable_pdf(state: AgentState, pdf_path: Path) -> AgentState:
    await ws_manager.send_log(state.session_id, "OCRAgent", "Extracting tables from searchable PDF...")

    # Try structured table extraction first
    tables = extract_tables_from_searchable_pdf(pdf_path)

    if tables:
        # Merge all tables into one dataset
        all_rows = []
        for table in tables:
            all_rows.extend(table)
        state.extracted_data = all_rows
        await ws_manager.send_log(
            state.session_id, "OCRAgent",
            f"Extracted {len(tables)} table(s), {len(all_rows)} total rows from searchable PDF"
        )
    else:
        # Fallback: extract raw text and ask Gemini to structure it
        pages = extract_text_from_searchable_pdf(pdf_path)
        raw_text = "\n\n".join(p["content"] for p in pages[:5])
        await ws_manager.send_log(state.session_id, "OCRAgent", "No tables found — asking Gemini to structure text...")
        state.extracted_data = await _gemini_structure_text(state, raw_text)

    return state


async def _process_scanned_pdf(state: AgentState, pdf_path: Path, page_count: int) -> AgentState:
    await ws_manager.send_log(state.session_id, "OCRAgent", "Converting scanned PDF pages to images...")

    temp_dir = workspace_service.get_temp() / state.session_id / "pdf_pages"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        pages_to_process = min(page_count, MAX_PAGES_FREE)
        if page_count > MAX_PAGES_FREE:
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                f"Large PDF ({page_count} pages) — processing first {MAX_PAGES_FREE} pages",
                level="warning"
            )

        image_paths = pdf_to_images(pdf_path, temp_dir)
        image_paths = image_paths[:pages_to_process]

        all_rows = []
        for i, img_path in enumerate(image_paths):
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                f"Processing page {i+1}/{len(image_paths)}..."
            )
            rows = await _ocr_single_image(state, img_path)
            all_rows.extend(rows)

        state.extracted_data = all_rows
        await ws_manager.send_log(
            state.session_id, "OCRAgent",
            f"Scanned PDF complete: {len(all_rows)} rows extracted from {len(image_paths)} page(s)"
        )
        return state

    finally:
        # Clean up temp images
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


# ── Image pipeline ────────────────────────────────────────────────────────────

async def _process_image(state: AgentState, image_path: Path) -> AgentState:
    await ws_manager.send_log(state.session_id, "OCRAgent", "Preprocessing image for OCR...")

    temp_dir = workspace_service.get_temp() / state.session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    preprocessed = preprocess_for_ocr(image_path, temp_dir / f"pre_{image_path.name}")

    rows = await _ocr_single_image(state, preprocessed)
    state.extracted_data = rows

    await ws_manager.send_log(
        state.session_id, "OCRAgent",
        f"Image OCR complete: {len(rows)} rows extracted"
    )
    return state


async def _ocr_single_image(state: AgentState, image_path: Path) -> list[dict]:
    """Run OCR on one image and return structured rows."""
    tables = ocr_engine.extract_tables_from_image(image_path)

    if not tables:
        # Fallback: extract raw text + Gemini structuring
        raw_text = ocr_engine.extract_text_from_image(image_path)
        if raw_text.strip():
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                "No tables detected — using Gemini to structure raw text"
            )
            return await _gemini_structure_text(state, raw_text)
        return []

    all_rows = []
    for table in tables:
        raw_rows = table.to_dicts()
        if raw_rows:
            # Gemini post-processing to clean OCR noise
            cleaned = await _gemini_clean_ocr_rows(state, raw_rows, table.confidence)
            all_rows.extend(cleaned)

    return all_rows


# ── Gemini post-processing ────────────────────────────────────────────────────

async def _gemini_clean_ocr_rows(
    state: AgentState,
    rows: list[dict],
    confidence: float
) -> list[dict]:
    """Use Gemini to fix OCR errors in extracted rows."""

    if confidence > 0.9 and len(rows) > 0:
        # High confidence — minimal cleanup
        await ws_manager.send_log(
            state.session_id, "OCRAgent",
            f"High confidence OCR ({confidence:.0%}) — skipping Gemini cleanup"
        )
        return rows

    sample = rows[:20]
    prompt = f"""
You are a data cleaning expert. Fix OCR errors in these extracted table rows.

Raw OCR output:
{json.dumps(sample, indent=2)}

Common OCR errors to fix:
- '0' vs 'O', '1' vs 'l', '5' vs 'S'
- Split words (e.g., "Invo ice" → "Invoice")
- Merged numbers (e.g., "1234 56" → "123456")
- Currency symbols misread (e.g., "S100" → "$100")
- Dates misread (e.g., "01/O5/23" → "01/05/23")
- Empty/null cells from merge artifacts

Return ONLY a JSON array of the corrected rows. Same structure, same keys.
Do not add or remove columns. Fix values only.
"""
    try:
        result = await gemini_service.analyze_json(prompt)
        if isinstance(result, list) and len(result) > 0:
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                f"Gemini cleaned {len(result)} OCR rows"
            )
            # Process remaining rows without Gemini if dataset is large
            if len(rows) > 20:
                return result + rows[20:]
            return result
    except Exception as e:
        logger.warning(f"Gemini OCR cleanup failed: {e}")

    return rows


async def _gemini_structure_text(state: AgentState, raw_text: str) -> list[dict]:
    """Ask Gemini to extract structured data from unstructured OCR text."""
    prompt = f"""
Extract structured tabular data from this OCR text.

Text:
{raw_text[:3000]}

Instructions:
- Identify column headers from the text
- Extract each data row
- Return as JSON array of objects with consistent keys

Return ONLY a JSON array. Example:
[
  {{"Invoice No": "INV-001", "Date": "2024-01-15", "Amount": "500.00"}},
  {{"Invoice No": "INV-002", "Date": "2024-01-16", "Amount": "750.00"}}
]

If no tabular data exists, return an array with one object containing a "content" key.
"""
    try:
        result = await gemini_service.analyze_json(prompt)
        if isinstance(result, list):
            await ws_manager.send_log(
                state.session_id, "OCRAgent",
                f"Gemini structured {len(result)} rows from raw text"
            )
            return result
    except Exception as e:
        logger.error(f"Gemini text structuring failed: {e}")

    # Final fallback: return raw text as single-column data
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    return [{"content": line} for line in lines]
