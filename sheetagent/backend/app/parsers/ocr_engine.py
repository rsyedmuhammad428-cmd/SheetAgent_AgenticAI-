"""
OCR Engine — Phase 3
Wraps EasyOCR and img2table for structured table extraction.
Falls back gracefully at each level.

Pipeline:
  image → preprocess → table detect → per-table OCR → structured rows
"""
from pathlib import Path
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class OCRCell:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1,y1,x2,y2


@dataclass
class OCRTable:
    rows: list[list[str]]           # [row][col] → text
    confidence: float
    page: int = 1
    source: str = "easyocr"

    def to_dicts(self) -> list[dict]:
        """Convert to list of row dicts using first row as header."""
        if not self.rows:
            return []
        headers = [h.strip() or f"col_{i}" for i, h in enumerate(self.rows[0])]
        result = []
        for row in self.rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            result.append(dict(zip(headers, [c.strip() for c in padded])))
        return result


class OCREngine:
    _reader = None  # lazy-loaded EasyOCR reader

    @classmethod
    def _get_reader(cls):
        if cls._reader is None:
            import easyocr
            cls._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return cls._reader

    def extract_tables_from_image(self, image_path: Path) -> list[OCRTable]:
        """Primary method: try img2table first, fallback to raw EasyOCR."""
        tables = self._try_img2table(image_path)
        if tables:
            return tables
        return self._easyocr_grid(image_path)

    def _try_img2table(self, image_path: Path) -> list[OCRTable]:
        """img2table gives the best structured table extraction."""
        try:
            from img2table.document import Image as Img2Image
            from img2table.ocr import EasyOCR as Img2EasyOCR

            ocr = Img2EasyOCR(lang=["en"])
            doc = Img2Image(src=str(image_path))
            extracted = doc.extract_tables(
                ocr=ocr,
                implicit_rows=True,
                borderless_tables=True,
                min_confidence=50,
            )

            tables = []
            for table in extracted:
                rows = []
                for row in table.content.values():
                    row_cells = [cell.value or "" for cell in row]
                    rows.append(row_cells)
                if rows:
                    tables.append(OCRTable(
                        rows=rows,
                        confidence=0.85,
                        source="img2table",
                    ))

            logger.info(f"img2table extracted {len(tables)} table(s) from {image_path.name}")
            return tables

        except Exception as e:
            logger.warning(f"img2table extraction failed: {e}")
            return []

    def _easyocr_grid(self, image_path: Path) -> list[OCRTable]:
        """
        EasyOCR fallback: reads all text with bounding boxes,
        then reconstructs a grid by clustering by Y position.
        """
        try:
            reader = self._get_reader()
            results = reader.readtext(str(image_path), detail=1, paragraph=False)

            if not results:
                return []

            # Sort by Y position (top-to-bottom)
            results.sort(key=lambda r: r[0][0][1])

            # Cluster into rows by Y proximity
            rows = _cluster_into_rows(results, y_tolerance=15)

            if not rows:
                return []

            # Sort each row left-to-right
            for row in rows:
                row.sort(key=lambda r: r[0][0][0])

            # Convert to text grid
            text_grid = [[cell[1] for cell in row] for row in rows]

            avg_conf = sum(
                cell[2] for row in results for cell in [row]
            ) / len(results) if results else 0.0

            return [OCRTable(rows=text_grid, confidence=avg_conf, source="easyocr")]

        except Exception as e:
            logger.error(f"EasyOCR grid extraction failed: {e}")
            return []

    def extract_text_from_image(self, image_path: Path) -> str:
        """Simple text extraction (non-table content)."""
        try:
            reader = self._get_reader()
            results = reader.readtext(str(image_path), detail=0, paragraph=True)
            return "\n".join(results)
        except Exception as e:
            logger.error(f"EasyOCR text extraction failed: {e}")
            return ""


def _cluster_into_rows(results: list, y_tolerance: int = 15) -> list[list]:
    """Group OCR results into rows by Y coordinate proximity."""
    if not results:
        return []

    rows: list[list] = []
    current_row = [results[0]]
    current_y = results[0][0][0][1]  # top-left Y of first bbox

    for result in results[1:]:
        bbox, text, conf = result
        y = bbox[0][1]

        if abs(y - current_y) <= y_tolerance:
            current_row.append(result)
        else:
            rows.append(current_row)
            current_row = [result]
            current_y = y

    if current_row:
        rows.append(current_row)

    return rows


# Singleton
ocr_engine = OCREngine()
