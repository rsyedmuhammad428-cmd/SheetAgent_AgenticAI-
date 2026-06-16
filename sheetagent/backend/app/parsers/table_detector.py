"""
Table Detector — Phase 3
Detects table regions in images using:
1. img2table (primary — best for structured tables)
2. OpenCV contour detection (fallback)
"""
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    page: int = 1

    def to_crop(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


def detect_tables_img2table(image_path: Path) -> list[TableRegion]:
    """Use img2table for robust table detection."""
    try:
        from img2table.document import Image as Img2TableImage
        from img2table.ocr import EasyOCR as Img2TableOCR

        doc = Img2TableImage(src=str(image_path))
        # Extract without OCR first — just structure
        tables = doc.extract_tables(implicit_rows=True, borderless_tables=True)

        regions = []
        for table in tables:
            bbox = table.bbox
            regions.append(TableRegion(
                x=bbox.x1, y=bbox.y1,
                width=bbox.x2 - bbox.x1,
                height=bbox.y2 - bbox.y1,
                confidence=0.9,
            ))

        logger.info(f"img2table detected {len(regions)} table(s)")
        return regions

    except Exception as e:
        logger.warning(f"img2table failed: {e} — falling back to OpenCV")
        return detect_tables_opencv(image_path)


def detect_tables_opencv(image_path: Path) -> list[TableRegion]:
    """
    OpenCV fallback: detect table-like regions by finding
    horizontal and vertical line intersections.
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    _, thresh = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY_INV)

    # Detect horizontal lines
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    # Detect vertical lines
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    # Combine
    grid = cv2.add(h_lines, v_lines)
    dilated = cv2.dilate(grid, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    img_area = img.shape[0] * img.shape[1]

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        aspect = w / h if h > 0 else 0

        # Filter: must be reasonably large and table-shaped
        if area > img_area * 0.01 and 0.2 < aspect < 10 and w > 100 and h > 50:
            regions.append(TableRegion(
                x=x, y=y, width=w, height=h,
                confidence=min(0.8, area / img_area * 10),
            ))

    # Sort top-to-bottom
    regions.sort(key=lambda r: r.y)
    logger.info(f"OpenCV detected {len(regions)} table region(s)")
    return regions


def crop_table_regions(image_path: Path, regions: list[TableRegion], output_dir: Path) -> list[Path]:
    """Save each detected table region as a separate cropped image."""
    img = cv2.imread(str(image_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    cropped_paths = []

    for i, region in enumerate(regions):
        crop = img[region.y:region.y + region.height, region.x:region.x + region.width]
        out_path = output_dir / f"table_{i+1:02d}.png"
        cv2.imwrite(str(out_path), crop)
        cropped_paths.append(out_path)

    return cropped_paths
