import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

EXTENSION_MAP = {
    ".csv":  "csv",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".xlsm": "excel",
    ".pdf":  "pdf",
    ".png":  "image",
    ".jpg":  "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif":  "image",
    ".txt":  "text",
}


def detect_file_type(file_path: Path) -> str:
    return EXTENSION_MAP.get(file_path.suffix.lower(), "unknown")


def parse_csv(file_path: Path) -> tuple[list[dict], list[str]]:
    df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records"), list(df.columns)


def parse_excel(file_path: Path, sheet_name: int | str = 0) -> tuple[list[dict], list[str]]:
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records"), list(df.columns)


def get_excel_sheet_names(file_path: Path) -> list[str]:
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    return xl.sheet_names
