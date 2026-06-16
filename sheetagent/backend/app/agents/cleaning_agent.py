import pandas as pd
from pathlib import Path
import json

from app.models.state import AgentState, AgentStatus, Suggestion
from app.services.ws_manager import ws_manager
from app.services.workspace_service import workspace_service
import uuid
import logging

logger = logging.getLogger(__name__)


def _normalize_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    changed = []
    for col in df.columns:
        if df[col].dtype == object:
            try:
                converted = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
                non_null = converted.notna().sum()
                if non_null > len(df) * 0.5:
                    df[col] = converted.dt.strftime("%Y-%m-%d").where(converted.notna(), df[col])
                    changed.append(col)
            except Exception:
                pass
    return df, changed


def _normalize_currency(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    changed = []
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().head(20).astype(str)
            if sample.str.contains(r'[\$£€¥]', regex=True).mean() > 0.3:
                df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors="coerce")
                changed.append(col)
    return df, changed


async def run_cleaning_agent(state: AgentState) -> AgentState:
    if state.status == AgentStatus.ERROR or not state.extracted_data:
        return state

    await ws_manager.send_log(state.session_id, "CleaningAgent", "Analyzing data quality...")

    try:
        df = pd.DataFrame(state.extracted_data)
        suggestions = []

        # Duplicates
        dup_count = df.duplicated().sum()
        if dup_count > 0:
            suggestions.append(Suggestion(
                id=str(uuid.uuid4()),
                title=f"Remove {dup_count} duplicate rows",
                description=f"Found {dup_count} identical rows in the dataset.",
                action="remove_duplicates",
                data={"count": int(dup_count)},
            ))

        # Missing values
        missing = df.isnull().sum()
        missing_cols = {col: int(cnt) for col, cnt in missing.items() if cnt > 0}
        if missing_cols:
            suggestions.append(Suggestion(
                id=str(uuid.uuid4()),
                title=f"Handle missing values in {len(missing_cols)} columns",
                description=f"Columns with missing data: {', '.join(list(missing_cols.keys())[:5])}",
                action="fill_missing",
                data={"missing_columns": missing_cols},
            ))

        # Date normalization
        df_temp, date_cols = _normalize_dates(df.copy())
        if date_cols:
            suggestions.append(Suggestion(
                id=str(uuid.uuid4()),
                title=f"Normalize date formats in {len(date_cols)} columns",
                description=f"Standardize to YYYY-MM-DD: {', '.join(date_cols)}",
                action="normalize_dates",
                data={"columns": date_cols},
            ))

        # Currency
        df_temp2, currency_cols = _normalize_currency(df.copy())
        if currency_cols:
            suggestions.append(Suggestion(
                id=str(uuid.uuid4()),
                title=f"Convert currency values in {len(currency_cols)} columns",
                description=f"Strip currency symbols, convert to numeric: {', '.join(currency_cols)}",
                action="normalize_currency",
                data={"columns": currency_cols},
            ))

        # Apply all cleaning to get cleaned data
        df_clean = df.copy()
        df_clean = df_clean.drop_duplicates()
        df_clean, _ = _normalize_dates(df_clean)
        df_clean, _ = _normalize_currency(df_clean)
        df_clean = df_clean.where(pd.notnull(df_clean), None)

        state.cleaned_data = df_clean.to_dict(orient="records")
        state.suggestions.extend(suggestions)

        # Save cleaned
        cleaned_dir = workspace_service.get_cleaned()
        cleaned_file = cleaned_dir / f"{state.session_id}_cleaned.json"
        cleaned_file.write_text(json.dumps(state.cleaned_data[:100], indent=2, default=str))

        await ws_manager.send_log(
            state.session_id, "CleaningAgent",
            f"Cleaning complete — {len(suggestions)} suggestions generated, {len(state.cleaned_data)} rows retained"
        )
        return state

    except Exception as e:
        logger.error(f"CleaningAgent error: {e}")
        state.error = str(e)
        state.status = AgentStatus.ERROR
        return state
