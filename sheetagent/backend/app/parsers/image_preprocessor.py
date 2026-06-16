"""
Image Preprocessor — Phase 3
Prepares images/PDF pages for OCR:
- grayscale conversion
- denoising
- deskewing
- contrast enhancement
- adaptive thresholding
"""
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def preprocess_for_ocr(image_path: Path, output_path: Path | None = None) -> Path:
    """
    Full preprocessing pipeline for an image before OCR.
    Returns path to preprocessed image.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # 3. Deskew
    deskewed = _deskew(denoised)

    # 4. Adaptive threshold — improves contrast for text
    thresh = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # 5. Sharpen
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(thresh, -1, kernel)

    # 6. Scale up small images (OCR works better on larger images)
    h, w = sharpened.shape
    if h < 1000 or w < 1000:
        scale = max(1000 / h, 1000 / w)
        sharpened = cv2.resize(sharpened, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    out_path = output_path or image_path.parent / f"{image_path.stem}_preprocessed.png"
    cv2.imwrite(str(out_path), sharpened)

    logger.info(f"Preprocessed: {image_path.name} → {out_path.name}")
    return out_path


def _deskew(image: np.ndarray) -> np.ndarray:
    """Detect and correct skew angle."""
    try:
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Only correct if skew is significant
        if abs(angle) < 0.5:
            return image

        h, w = image.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated
    except Exception:
        return image


def pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 300) -> list[Path]:
    """
    Convert each PDF page to a high-resolution image.
    Requires poppler-utils (apt-get install poppler-utils).
    """
    try:
        from pdf2image import convert_from_path
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = convert_from_path(str(pdf_path), dpi=dpi)
        image_paths = []

        for i, page in enumerate(pages):
            out_path = output_dir / f"page_{i+1:03d}.png"
            page.save(str(out_path), "PNG")
            image_paths.append(out_path)

        logger.info(f"PDF → {len(image_paths)} page images: {pdf_path.name}")
        return image_paths

    except ImportError:
        raise RuntimeError("pdf2image not installed. Run: pip install pdf2image")
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}")


def crop_to_content(image_path: Path) -> Path:
    """Remove large white borders from scanned documents."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(img, 240, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return image_path

    x, y, w, h = cv2.boundingRect(coords)
    padding = 20
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(img.shape[1] - x, w + 2 * padding)
    h = min(img.shape[0] - y, h + 2 * padding)

    cropped = cv2.imread(str(image_path))[y:y+h, x:x+w]
    cv2.imwrite(str(image_path), cropped)
    return image_path
