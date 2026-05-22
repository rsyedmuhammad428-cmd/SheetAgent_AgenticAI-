"""
Instruction Parser — Phase 5
Converts natural language user instructions into a structured ExcelConfig.

Examples:
  "I want an invoice template with company logo area, item table, tax calculation"
  "Create a monthly sales report with charts, totals row, color coded by region"
  "Make a student grade sheet with pass/fail conditional formatting"
  "Budget tracker with income, expenses, balance formula, bar chart"
"""
from pydantic import BaseModel
from typing import Optional
import json

from app.services.gemini_service import gemini_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ColumnSpec(BaseModel):
    name: str
    type: str = "text"          # text | number | currency | date | percentage | formula
    width: int = 20
    formula: Optional[str] = None
    required: bool = False


class SheetSpec(BaseModel):
    name: str
    columns: list[ColumnSpec]
    has_totals_row: bool = False
    has_filters: bool = True
    freeze_header: bool = True
    sample_rows: int = 5        # number of sample/placeholder rows to add


class ConditionalRule(BaseModel):
    sheet: str
    column: str
    rule_type: str              # "greater_than" | "less_than" | "equals" | "contains"
    value: str
    format: str                 # "green" | "red" | "amber" | "bold"


class ChartSpec(BaseModel):
    title: str
    chart_type: str             # bar | line | pie
    sheet: str
    category_column: str
    value_column: str


class ExcelConfig(BaseModel):
    title: str
    description: str
    schema_type: str
    sheets: list[SheetSpec]
    conditional_rules: list[ConditionalRule] = []
    charts: list[ChartSpec] = []
    has_summary_sheet: bool = True
    color_theme: str = "professional"  # professional | minimal | colorful
    special_features: list[str] = []  # e.g. ["dropdowns", "data_validation", "password_protect"]


async def parse_instruction_to_config(user_instruction: str, preferences: dict = {}) -> ExcelConfig:
    """
    Parse a natural language instruction into a full ExcelConfig.
    """
    prompt = f"""
You are an Excel architect. Convert the user's instruction into a detailed Excel workbook specification.

User instruction: "{user_instruction}"

User preferences:
- Date format: {preferences.get('date_format', 'YYYY-MM-DD')}
- Currency: {preferences.get('currency', 'USD')}
- Theme: {preferences.get('excel_theme', 'professional')}
- Default chart: {preferences.get('chart_style', 'bar')}

Return a JSON object with this exact structure:
{{
  "title": "Workbook title",
  "description": "What this workbook does",
  "schema_type": "invoice|sales_report|inventory|hr_records|student_data|financial|generic",
  "sheets": [
    {{
      "name": "Sheet name",
      "columns": [
        {{
          "name": "Column Name",
          "type": "text|number|currency|date|percentage|formula",
          "width": 20,
          "formula": "=SUM(B2:B100) or null",
          "required": true
        }}
      ],
      "has_totals_row": true,
      "has_filters": true,
      "freeze_header": true,
      "sample_rows": 5
    }}
  ],
  "conditional_rules": [
    {{
      "sheet": "Sheet name",
      "column": "Column name",
      "rule_type": "greater_than|less_than|equals|contains",
      "value": "threshold value",
      "format": "green|red|amber|bold"
    }}
  ],
  "charts": [
    {{
      "title": "Chart title",
      "chart_type": "bar|line|pie",
      "sheet": "source sheet name",
      "category_column": "column for X axis",
      "value_column": "column for Y axis"
    }}
  ],
  "has_summary_sheet": true,
  "color_theme": "professional|minimal|colorful",
  "special_features": []
}}

Rules:
- Always include at least one sheet with meaningful columns
- Add formulas for totals, calculations where appropriate
- Add conditional formatting for status/score/amount columns
- Add charts if user mentions visualization or reporting
- Be specific with column names matching the domain
- Include sample_rows: 5 so user sees a template structure
"""

    try:
        result = await gemini_service.analyze_json(prompt)
        config = ExcelConfig(**result)
        logger.info("instruction_parsed", title=config.title, sheets=len(config.sheets))
        return config
    except Exception as e:
        logger.error("instruction_parse_error", error=str(e))
        # Return a sensible default
        return ExcelConfig(
            title="Custom Workbook",
            description=user_instruction,
            schema_type="generic",
            sheets=[SheetSpec(
                name="Data",
                columns=[
                    ColumnSpec(name="ID", type="number"),
                    ColumnSpec(name="Name", type="text"),
                    ColumnSpec(name="Value", type="number"),
                    ColumnSpec(name="Date", type="date"),
                    ColumnSpec(name="Notes", type="text"),
                ],
                has_totals_row=True,
            )],
        )
