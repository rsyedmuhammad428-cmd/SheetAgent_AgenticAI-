"""
Diff Service — Phase 2
Computes before/after diff between raw and cleaned data.
Used to show users exactly what the Cleaning Agent changed.
"""
import pandas as pd
from app.models.state import DiffEntry


def compute_diff(
    original: list[dict],
    cleaned: list[dict],
    max_diffs: int = 200
) -> list[DiffEntry]:
    """
    Compare original vs cleaned datasets row by row.
    Returns a list of DiffEntry objects describing each change.
    """
    entries: list[DiffEntry] = []

    df_orig = pd.DataFrame(original)
    df_clean = pd.DataFrame(cleaned)

    # Align on common columns
    common_cols = [c for c in df_orig.columns if c in df_clean.columns]

    orig_rows = min(len(df_orig), len(df_clean))

    for row_idx in range(orig_rows):
        for col in common_cols:
            val_orig = df_orig.iloc[row_idx][col]
            val_clean = df_clean.iloc[row_idx][col]

            orig_str = str(val_orig) if val_orig is not None else ""
            clean_str = str(val_clean) if val_clean is not None else ""

            if orig_str != clean_str:
                entries.append(DiffEntry(
                    row=row_idx + 2,  # +2 for 1-indexed + header
                    column=col,
                    before=val_orig,
                    after=val_clean,
                    change_type="modified",
                ))
                if len(entries) >= max_diffs:
                    return entries

    # Detect removed rows (original has more rows)
    if len(df_orig) > len(df_clean):
        removed = len(df_orig) - len(df_clean)
        for i in range(removed):
            entries.append(DiffEntry(
                row=orig_rows + i + 2,
                column="*",
                before="[row existed]",
                after="[row removed — duplicate]",
                change_type="removed",
            ))
            if len(entries) >= max_diffs:
                break

    return entries


def summarize_diff(diff: list[DiffEntry]) -> dict:
    modified = sum(1 for d in diff if d.change_type == "modified")
    removed = sum(1 for d in diff if d.change_type == "removed")
    added = sum(1 for d in diff if d.change_type == "added")

    affected_columns: dict[str, int] = {}
    for d in diff:
        if d.column != "*":
            affected_columns[d.column] = affected_columns.get(d.column, 0) + 1

    return {
        "total_changes": len(diff),
        "modified_cells": modified,
        "removed_rows": removed,
        "added_rows": added,
        "affected_columns": affected_columns,
    }
