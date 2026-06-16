"""
PDF Parser — Phase 3
Smart PDF handling:
- Searchable PDF → pypdf text extraction (fast, accurate)
- Scanned PDF → pdf2image → OCR pipeline
- Mixed PDF → per-page decision
"""
from pathlib import Path
import logging
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS_PER_PAGE = 50  # below this → treat page as scanned


def is_searchable_pdf(pdf_path: Path) -> tuple[bool, int]:
    """
    Check if PDF has extractable text.
    Returns (is_searchable, total_char_count).
    """
    try:
        reader = PdfReader(str(pdf_path))
        total_chars = sum(len(page.extract_text() or "") for page in reader.pages)
        is_searchable = total_chars > MIN_TEXT_CHARS_PER_PAGE * len(reader.pages)
        return is_searchable, total_chars
    except Exception:
        return False, 0


def extract_text_from_searchable_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract structured text from searchable PDF.
    Returns list of dicts with page + content.
    """
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": i + 1, "content": text.strip()})
    return pages


def extract_tables_from_searchable_pdf(pdf_path: Path) -> list[list[dict]]:
    """
    Try to extract tables from searchable PDF using pypdf.
    Returns list of tables, each table is list of row dicts.
    """
    try:
        import pdfplumber
        tables_all = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    headers = [str(h or f"col_{i}").strip() for i, h in enumerate(table[0])]
                    rows = []
                    for row in table[1:]:
                        row_dict = {
                            headers[i]: str(cell or "").strip()
                            for i, cell in enumerate(row)
                            if i < len(headers)
                        }
                        rows.append(row_dict)
                    if rows:
                        tables_all.append(rows)
        return tables_all
    except ImportError:
        logger.warning("pdfplumber not installed — falling back to text extraction")
        return []
    except Exception as e:
        logger.error(f"pdfplumber table extraction failed: {e}")
        return []


def get_pdf_page_count(pdf_path: Path) -> int:
    try:
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception:
        return 0
