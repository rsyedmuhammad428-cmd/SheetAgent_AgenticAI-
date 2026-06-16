"""
Analytics Agent — Phase 2
Answers natural language questions about the dataset:
averages, trends, comparisons, outliers, basic forecasting.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json

from app.models.state import AgentState
from app.services.gemini_service import gemini_service
from app.services.ws_manager import ws_manager
import logging

logger = logging.getLogger(__name__)


class AnalyticsResult:
    def __init__(self, question: str, answer: str, data: dict | None = None):
        self.question = question
        self.answer = answer
        self.data = data or {}

    def to_dict(self):
        return {"question": self.question, "answer": self.answer, "data": self.data}


async def run_analytics_agent(
    state: AgentState,
    question: str
) -> AnalyticsResult:
    """Answer a natural language question about the dataset."""

    await ws_manager.send_log(state.session_id, "AnalyticsAgent", f"Analyzing: '{question}'")

    data = state.cleaned_data or state.extracted_data or []
    if not data:
        return AnalyticsResult(question, "No data available to analyze.")

    try:
        df = pd.DataFrame(data)

        # Compute stats to pass to Gemini
        stats = _compute_stats(df)

        answer = await _gemini_answer(question, stats, df.columns.tolist(), len(df))
        result = AnalyticsResult(question, answer, stats)

        await ws_manager.send_log(
            state.session_id, "AnalyticsAgent",
            f"Analysis complete for: '{question}'"
        )
        return result

    except Exception as e:
        logger.error(f"AnalyticsAgent error: {e}")
        return AnalyticsResult(question, f"Analysis failed: {e}")


def _compute_stats(df: pd.DataFrame) -> dict:
    stats = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numeric_cols[:8]:  # limit to 8 numeric cols
        col_stats = {
            "mean": round(float(df[col].mean()), 2) if not df[col].isna().all() else None,
            "median": round(float(df[col].median()), 2) if not df[col].isna().all() else None,
            "min": round(float(df[col].min()), 2) if not df[col].isna().all() else None,
            "max": round(float(df[col].max()), 2) if not df[col].isna().all() else None,
            "sum": round(float(df[col].sum()), 2) if not df[col].isna().all() else None,
            "std": round(float(df[col].std()), 2) if not df[col].isna().all() else None,
            "null_count": int(df[col].isna().sum()),
        }

        # Detect outliers using IQR
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        outliers = df[(df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)][col]
        col_stats["outlier_count"] = len(outliers)
        col_stats["outlier_values"] = outliers.head(3).tolist()

        stats[col] = col_stats

    # Categorical summaries
    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    stats["_categorical"] = {}
    for col in cat_cols[:5]:
        stats["_categorical"][col] = df[col].value_counts().head(5).to_dict()

    stats["_total_rows"] = len(df)
    stats["_total_cols"] = len(df.columns)

    return stats


async def _gemini_answer(question: str, stats: dict, columns: list, row_count: int) -> str:
    prompt = f"""
You are a data analyst. Answer the question using the computed statistics.

Question: "{question}"

Dataset: {row_count} rows, columns: {columns}

Statistics:
{json.dumps(stats, indent=2, default=str)}

Rules:
- Give a direct, concise answer (2-4 sentences)
- Include specific numbers from the stats
- If the question can't be answered from stats alone, say so clearly
- Format numbers with commas for readability
"""
    try:
        return await gemini_service.analyze(prompt)
    except Exception as e:
        return f"Could not analyze: {e}"


# Convenience: basic forecast using linear regression
def simple_forecast(values: list[float], periods: int = 3) -> list[float]:
    """Simple linear regression forecast."""
    if len(values) < 2:
        return []
    x = np.arange(len(values))
    coeffs = np.polyfit(x, values, 1)
    future_x = np.arange(len(values), len(values) + periods)
    return [round(float(np.polyval(coeffs, xi)), 2) for xi in future_x]
