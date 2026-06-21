"""
SheetAgent AI — Phase 7: intelligence_engine.py
REPLACE: backend/app/agents/intelligence_engine.py

Phase 7 Fix:
  When real extracted_data is available, the design_workbook prompt now:
  1. Shows Gemini the ACTUAL column names from the file
  2. Tells Gemini to use those exact names in the first sheet's columns
  3. Sets sample_rows = actual row count (not a fixed 8)
  This ensures the design spec matches the real data so excel_generator
  doesn't fall back to sample data.

  All Phase 6 logic preserved — only the prompt wording changed for data-aware calls.
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional
from app.agents.rate_limiter import call_with_retry

logger = logging.getLogger(__name__)


class IntelligenceEngine:

    def __init__(self):
        from app.services.gemini_service import gemini_service
        self.gemini = gemini_service

    # ── Step 1: Understand task (unchanged from Phase 6) ─────────────────────

    async def understand_task(
        self,
        user_message: str,
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        conversation_history: Optional[list] = None,
    ) -> dict:
        context_parts = []
        if file_content:
            context_parts.append(f"=== UPLOADED FILE: {file_name or 'file'} ===\n{file_content[:6000]}")
        if conversation_history:
            recent = conversation_history[-4:]
            history_str = "\n".join(
                f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
            )
            context_parts.append(f"=== CONVERSATION HISTORY ===\n{history_str}")

        context = "\n\n".join(context_parts)

        prompt = f"""You are an expert data analyst and Excel architect.

Analyze this user request DEEPLY. The user may have given specific instructions
about charts, formatting, colors, or what to highlight — extract ALL of them.

USER MESSAGE: "{user_message}"

{context}

Return a JSON task description:
{{
  "task_type": "create_from_scratch | process_uploaded_file | analyze_data | modify_existing",
  "domain": "detected domain e.g. education, hr, finance, sales, inventory, healthcare, etc.",
  "workbook_title": "Specific, descriptive title based on the actual task",
  "workbook_purpose": "What this workbook achieves for the user",
  "complexity": "simple | medium | complex",
  "requires_file_data": true/false,
  "user_intent_summary": "One sentence summary of exactly what the user wants",
  "key_requirements": ["list", "of", "specific", "requirements from the message"],
  "explicit_chart_instructions": "Exact chart requirement from user message, e.g. 'bar graph by subject' or 'pie chart by territory' — empty string if none mentioned",
  "chart_category_column": "The EXACT column name the user said to group the chart by, e.g. 'Subject' or 'Territory' — empty string if not specified",
  "chart_value_column": "The EXACT column name to use as the chart value, e.g. 'Sales' or 'Score' — empty string if not specified",
  "chart_type_requested": "bar | line | pie | column — from user message, default bar",
  "conditional_formatting_instructions": "Any pass/fail/threshold/color instructions from the user, e.g. 'red for fail, green for pass' or 'red if loss'",
  "heading_title": "The document heading/title the user wants at the top of the sheet, e.g. 'Monthly Sales Report' — derive from context if not explicit",
  "suggested_sheets": [
    {{
      "name": "Sheet name",
      "purpose": "What this sheet does",
      "key_columns": ["col1", "col2"],
      "has_calculations": true/false,
      "has_charts": true/false
    }}
  ],
  "color_theme": "professional | blue | green | orange | purple | dark",
  "style_notes": "Any specific style requirements mentioned"
}}"""

        try:
            result = await call_with_retry(self.gemini.analyze_json, prompt)
            if isinstance(result, dict) and result.get("workbook_title"):
                logger.info(f"[Phase7] Task understood: {result.get('user_intent_summary','')[:80]}")
                return result
        except Exception as e:
            from app.agents.quota_helper import is_quota_error, is_provider_error
            if is_quota_error(e) or is_provider_error(e): raise
            logger.error(f"[Phase7] Task understanding failed: {e}")

        return {
            "task_type": "create_from_scratch",
            "domain": self._detect_domain_keywords(user_message),
            "workbook_title": self._make_title(user_message),
            "workbook_purpose": user_message,
            "complexity": "medium",
            "requires_file_data": bool(file_content),
            "user_intent_summary": user_message[:100],
            "key_requirements": [user_message],
            "suggested_sheets": [{"name": "Data", "purpose": "Main data", "key_columns": [],
                                   "has_calculations": True, "has_charts": False}],
            "color_theme": "professional",
            "style_notes": "",
            "explicit_chart_instructions": self._extract_chart_instructions(user_message),
            "chart_category_column": "",
            "chart_value_column": "",
            "chart_type_requested": self._extract_chart_type(user_message),
            "conditional_formatting_instructions": "",
            "heading_title": "",
        }

    # ── Step 2: Design workbook ───────────────────────────────────────────────

    async def design_workbook(
        self,
        task: dict,
        file_content: Optional[str] = None,
        extracted_data: Optional[list] = None,
        extracted_columns: Optional[list] = None,
    ) -> dict:
        """
        Phase 7 ROOT CAUSE FIX:
        When real data is available (extracted_columns + extracted_data),
        we SKIP Gemini column design entirely for the first sheet.
        We build the first sheet spec directly from the actual column names.
        Gemini is only used for: title, theme, charts, conditional rules.

        This guarantees excel_generator always receives column names that
        exactly match the real_data dict keys — no mismatch, no sample fallback.
        """
        has_real_data    = bool(extracted_data and len(extracted_data) > 0)
        has_real_columns = bool(extracted_columns and len(extracted_columns) >= 1)

        # ── FAST PATH: real data available → build first sheet spec directly ──
        # Do NOT ask Gemini to design columns when we already know them exactly.
        if has_real_columns and has_real_data:
            logger.info(f"[Phase7] Real data fast path — {len(extracted_columns)} cols, {len(extracted_data)} rows")
            return self._build_design_from_real_data(
                task=task,
                real_columns=extracted_columns,
                real_data=extracted_data,
                file_content=file_content,
            )

        # ── SLOW PATH: no real data → ask Gemini to design everything ─────────
        data_context = ""
        if file_content:
            data_context = f"\n\nFile content preview:\n{file_content[:3000]}"

        prompt = f"""You are an expert Excel architect. Design a complete, professional workbook.

TASK UNDERSTANDING:
{json.dumps(task, indent=2)}
{data_context}

Design a complete workbook specification. Rules:
- Title must be specific to the task, NEVER "Custom Workbook"
- Write REAL Excel formulas (=SUM, =IF, =AVERAGE etc.) with correct column letters
- Add meaningful conditional formatting rules
- Add charts only where they genuinely help
- sample_rows: 8

Return ONLY valid JSON (start with {{, no markdown):
{{
  "title": "Specific workbook title matching the task",
  "description": "What this workbook does",
  "schema_type": "invoice|sales_report|inventory|hr_records|student_data|financial|generic",
  "color_theme": "professional|minimal|colorful",
  "has_summary_sheet": true,
  "sheets": [
    {{
      "name": "Descriptive Sheet Name",
      "columns": [
        {{
          "name": "Exact Column Name",
          "type": "text|number|currency|date|percentage|formula",
          "width": 20,
          "formula": "=FORMULA or null",
          "required": true,
          "dropdown_values": ["opt1", "opt2"] or null
        }}
      ],
      "has_totals_row": true,
      "has_filters": true,
      "freeze_header": true,
      "sample_rows": 8
    }}
  ],
  "conditional_rules": [],
  "charts": []
}}"""

        try:
            result = await call_with_retry(self.gemini.analyze_json, prompt)
            if isinstance(result, dict) and self._is_valid_design(result):
                logger.info(f"[Phase7] Gemini design: '{result.get('title')}' — {len(result.get('sheets',[]))} sheets")
                return result
            logger.warning(f"[Phase7] Invalid design from Gemini: {str(result)[:200]}")
        except Exception as e:
            from app.agents.quota_helper import is_quota_error, is_provider_error
            if is_quota_error(e) or is_provider_error(e): raise
            logger.error(f"[Phase7] Workbook design failed: {e}")

        return await self._generate_domain_design(task, extracted_columns, extracted_data)

    def _build_design_from_real_data(
        self,
        task: dict,
        real_columns: list,
        real_data: list,
        file_content: Optional[str] = None,
    ) -> dict:
        """
        Build complete workbook design using ONLY the actual extracted column names.
        No Gemini involvement in column naming — zero chance of mismatch.
        Gemini-like intelligence applied via keyword inference for types/widths.
        """
        title  = task.get("workbook_title", "Data Workbook")
        domain = task.get("domain", "generic")

        col_specs = []
        numeric_col_letters = []

        for i, col in enumerate(real_columns):
            col_type   = _infer_col_type(col)
            col_lower  = col.lower()
            formula    = None
            dropdown   = None

            # Auto-detect dropdown candidates
            if col_lower in ("status", "state"):
                dropdown = ["Active", "Inactive", "Pending", "Completed"]
            elif col_lower == "grade":
                dropdown = ["Pass", "Fail", "A+", "A", "B+", "B", "C", "D", "F"]
            elif "department" in col_lower or "dept" in col_lower:
                dropdown = ["HR", "Finance", "Engineering", "Sales", "Operations", "Marketing"]

            col_letter = chr(65 + i)  # A, B, C...
            if col_type in ("number", "currency"):
                numeric_col_letters.append((col, col_letter))

            col_specs.append({
                "name":             col,
                "type":             col_type,
                "width":            max(int(len(col)) + 6, 14),
                "formula":          formula,
                "required":         False,
                "dropdown_values":  dropdown,
            })

        num_rows = min(len(real_data), 500)
        sheet_name = _sheet_name_from_task(task)

        # Build conditional rules — honour explicit user instructions
        cond_rules = []
        cond_instr = task.get("conditional_formatting_instructions", "").lower()

        for col in real_columns:
            col_lower = col.lower()

            # Grade/pass/fail columns
            if any(w in col_lower for w in ["grade", "pass", "fail", "result", "status_result"]):
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "Pass", "format": "green"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "Fail", "format": "red"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "A+", "format": "green"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "A", "format": "green"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "F", "format": "red"})

            # Profit/loss/gain columns — numbers < 0 red, > 0 green
            elif any(w in col_lower for w in ["profit", "loss", "gain", "net", "balance"]):
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "less_than", "value": "0", "format": "red"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "greater_than", "value": "0", "format": "green"})

            # Status column
            elif col_lower == "status":
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "Active", "format": "green"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "Inactive", "format": "red"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "equals", "value": "Pending", "format": "amber"})

            # Score/marks — apply red if <50, green if >=80 (unless user overrides)
            elif any(w in col_lower for w in ["score", "marks", "points", "total"]):
                threshold_fail = 50
                threshold_pass = 80
                # User can say "fail below 40" or "pass above 70"
                if cond_instr:
                    m_fail = __import__("re").search(r"fail.*?(\d+)|below.*?(\d+)|less.*?(\d+)", cond_instr)
                    m_pass = __import__("re").search(r"pass.*?(\d+)|above.*?(\d+)|greater.*?(\d+)", cond_instr)
                    if m_fail:
                        threshold_fail = int(next(x for x in m_fail.groups() if x))
                    if m_pass:
                        threshold_pass = int(next(x for x in m_pass.groups() if x))
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "less_than", "value": str(threshold_fail), "format": "red"})
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "greater_than", "value": str(threshold_pass - 1), "format": "green"})

            # Commission/sales — highlight high values green
            elif any(w in col_lower for w in ["commission", "revenue", "sales", "amount"]):
                cond_rules.append({"sheet": sheet_name, "column": col,
                                   "rule_type": "less_than", "value": "0", "format": "red"})

        # Build charts — honour explicit user instructions first
        charts = []
        text_cols   = [c["name"] for c in col_specs if c["type"] == "text"]
        number_cols = [c["name"] for c in col_specs if c["type"] in ("number", "currency")]

        explicit_cat = task.get("chart_category_column", "").strip()
        explicit_val = task.get("chart_value_column", "").strip()
        chart_type   = task.get("chart_type_requested", "bar").strip() or "bar"
        chart_instr  = task.get("explicit_chart_instructions", "").strip()

        # Resolve category column: exact match → case-insensitive match → fallback
        cat_col = None
        val_col = None
        all_col_names = [c["name"] for c in col_specs]

        if explicit_cat:
            cat_col = next((n for n in all_col_names if n.lower() == explicit_cat.lower()), None)
            if not cat_col:  # partial match
                cat_col = next((n for n in all_col_names if explicit_cat.lower() in n.lower()), None)
            if not cat_col and explicit_cat.lower() in ["subject", "subjects", "column", "columns", "month", "months", "category", "categories"]:
                cat_col = "__HEADERS__"
                
        if not cat_col:
            cat_col = text_cols[0] if text_cols else (all_col_names[0] if all_col_names else None)

        if cat_col == "__HEADERS__":
            val_col = "__TOTALS__"
        else:
            if explicit_val:
                val_col = next((n for n in all_col_names if n.lower() == explicit_val.lower()), None)
                if not val_col:
                    val_col = next((n for n in all_col_names if explicit_val.lower() in n.lower()), None)
            if not val_col:
                val_col = number_cols[0] if number_cols else (all_col_names[1] if len(all_col_names) > 1 else None)

        if cat_col and val_col and (chart_instr or (text_cols and number_cols)):
            chart_title = chart_instr or f"{val_col} by {cat_col}"
            charts.append({
                "title":           chart_title,
                "chart_type":      chart_type,
                "sheet":           sheet_name,
                "category_column": cat_col,
                "value_column":    val_col,
            })
            logger.info(f"[Phase7] Chart: {chart_type} — {val_col} by {cat_col}")

        heading = task.get("heading_title", "").strip() or title

        return {
            "title":            title,
            "heading_title":    heading,
            "description":      f"{title} — {len(real_data)} rows, {len(real_columns)} columns",
            "schema_type":      domain if domain in ["invoice","sales_report","inventory","hr_records","student_data","financial"] else "generic",
            "color_theme":      task.get("color_theme", "professional"),
            "has_summary_sheet": True,
            "sheets": [{
                "name":          sheet_name,
                "columns":       col_specs,
                "has_totals_row": True,
                "has_filters":   True,
                "freeze_header": True,
                "sample_rows":   num_rows,
            }],
            "conditional_rules": cond_rules,
            "charts":           charts,
        }

    def _enforce_real_columns(self, design: dict, real_columns: list) -> dict:
        """
        Phase 7: Overwrite the first sheet's column names with the actual
        extracted column names. This guarantees excel_generator finds a match.
        """
        if not design.get("sheets") or not real_columns:
            return design

        first_sheet = design["sheets"][0]
        existing_cols = first_sheet.get("columns", [])

        # Build a lookup of existing col specs by lowercased name
        existing_map = {c["name"].lower(): c for c in existing_cols}

        new_cols = []
        for real_col in real_columns:
            # Check if Gemini happened to match
            existing = existing_map.get(real_col.lower())
            if existing:
                col_spec = dict(existing)
                col_spec["name"] = real_col  # preserve exact casing
            else:
                # Infer type from column name
                col_type = _infer_col_type(real_col)
                col_spec = {
                    "name": real_col,
                    "type": col_type,
                    "width": max(len(real_col) + 6, 14),
                    "formula": None,
                    "required": False,
                    "dropdown_values": None,
                }
            new_cols.append(col_spec)

        design["sheets"][0]["columns"] = new_cols
        return design

    async def _generate_domain_design(
        self,
        task: dict,
        extracted_columns: Optional[list] = None,
        extracted_data: Optional[list] = None,
    ) -> dict:
        domain = task.get("domain", "generic")
        title  = task.get("workbook_title", task.get("user_intent_summary", "Data Workbook"))
        intent = task.get("user_intent_summary", "")

        if extracted_columns and len(extracted_columns) >= 2:
            return self._build_from_actual_columns(title, extracted_columns, extracted_data or [], domain)

        simple_prompt = f"""Design an Excel workbook for: "{intent}"
Domain: {domain}

Return JSON with these exact fields:
- title: string (specific title, not "Custom Workbook")
- description: string
- schema_type: string
- color_theme: "professional"
- has_summary_sheet: true
- sheets: array of sheet objects, each with name, columns array, has_totals_row, has_filters, freeze_header, sample_rows:8
- Each column: name (specific), type (text/number/currency/date/percentage/formula), width (int), formula (string or null), required (bool), dropdown_values (array or null)
- conditional_rules: array
- charts: array

Use domain-specific column names. Return ONLY JSON starting with {{"""

        try:
            result = await call_with_retry(self.gemini.analyze_json, simple_prompt)
            if isinstance(result, dict) and result.get("sheets"):
                return result
        except Exception as e:
            from app.agents.quota_helper import is_quota_error, is_provider_error
            if is_quota_error(e) or is_provider_error(e): raise
            logger.error(f"[Phase7] Domain design also failed: {e}")

        return self._build_from_actual_columns(
            title,
            extracted_columns or self._get_domain_columns(domain),
            extracted_data or [],
            domain,
        )

    def _build_from_actual_columns(self, title: str, columns: list, data: list, domain: str) -> dict:
        col_specs = []
        for col in columns:
            col_lower  = col.lower()
            col_type   = _infer_col_type(col)
            dropdown   = None

            if col_lower in ["status", "state"]:
                dropdown = ["Active", "Inactive", "Pending", "Completed"]
            elif col_lower == "grade":
                dropdown = ["A+", "A", "B+", "B", "C", "D", "F"]
            elif "department" in col_lower or "dept" in col_lower:
                dropdown = ["HR", "Finance", "Engineering", "Sales", "Operations", "Marketing"]

            col_specs.append({
                "name": col,
                "type": col_type,
                "width": max(int(len(col)) + 6, 15),
                "formula": None,
                "required": False,
                "dropdown_values": dropdown,
            })

        return {
            "title": title,
            "description": f"Excel workbook — {len(columns)} columns, {len(data)} rows",
            "schema_type": domain if domain in ["invoice","sales_report","inventory","hr_records","student_data","financial"] else "generic",
            "color_theme": "professional",
            "has_summary_sheet": True,
            "sheets": [{
                "name": "Data",
                "columns": col_specs,
                "has_totals_row": True,
                "has_filters": True,
                "freeze_header": True,
                "sample_rows": min(len(data), 10) if data else 8,
            }],
            "conditional_rules": [],
            "charts": [],
        }

    def _get_domain_columns(self, domain: str) -> list:
        defaults = {
            "education":  ["Student ID", "Full Name", "Math", "Science", "English", "Total", "Grade"],
            "hr":         ["Employee ID", "Full Name", "Department", "Basic Salary", "Allowances", "Deductions", "Net Salary"],
            "sales":      ["Date", "Salesperson", "Product", "Units Sold", "Unit Price", "Revenue", "Target"],
            "invoice":    ["Invoice No", "Date", "Client Name", "Item", "Quantity", "Unit Price", "Amount", "Tax", "Total"],
            "inventory":  ["SKU", "Product Name", "Category", "Stock Qty", "Unit Cost", "Total Value", "Reorder Level"],
            "finance":    ["Date", "Description", "Category", "Income", "Expense", "Balance", "Notes"],
        }
        for key, cols in defaults.items():
            if key in domain.lower():
                return cols
        return ["ID", "Name", "Category", "Value", "Date", "Status", "Notes"]

    def _is_valid_design(self, result: dict) -> bool:
        if not isinstance(result, dict) or not result.get("sheets"):
            return False
        title = result.get("title", "").lower()
        if title in ["custom workbook", "workbook", "", "excel workbook", "my workbook"]:
            return False
        for sheet in result["sheets"]:
            if not sheet.get("columns"):
                return False
            for col in sheet["columns"]:
                name = col.get("name", "").lower()
                if name in ["column", "col", "field", "column 1", "column1", "value", ""]:
                    return False
        return True

    def _detect_domain_keywords(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["student", "mark", "grade", "exam", "subject", "class", "school"]):
            return "education"
        if any(w in t for w in ["salary", "employee", "hr", "payroll", "staff", "department"]):
            return "hr"
        if any(w in t for w in ["invoice", "bill", "client", "payment"]):
            return "invoice"
        if any(w in t for w in ["sales", "revenue", "target", "salesperson"]):
            return "sales"
        if any(w in t for w in ["inventory", "stock", "product", "warehouse", "sku"]):
            return "inventory"
        if any(w in t for w in ["budget", "expense", "income", "finance", "cost"]):
            return "finance"
        return "generic"

    def _make_title(self, text: str) -> str:
        stop_words = {"create", "make", "build", "generate", "a", "an", "the", "me",
                      "please", "i", "want", "need", "give", "my", "for", "of"}
        words = text.strip().split()
        meaningful = [w for w in words if w.lower() not in stop_words]
        if meaningful:
            return " ".join(meaningful[:7]).title()
        return text[:50].title()

    def _extract_chart_type(self, text: str) -> str:
        """Extract requested chart type from user message."""
        text_lower = text.lower()
        if "pie" in text_lower:
            return "pie"
        elif "line" in text_lower:
            return "line"
        elif "area" in text_lower:
            return "area"
        elif "bar" in text_lower or "column" in text_lower:
            return "bar"
        return "bar"  # default

    def _extract_chart_instructions(self, text: str) -> str:
        """Extract user's chart instructions, e.g., 'bar graph by subject'."""
        import re
        # Look for patterns like "bar chart by X", "pie graph of Y", etc.
        patterns = [
            r"(bar|pie|line|column|area)\s+(chart|graph|plot)(?:\s+(?:by|of|with)\s+([a-zA-Z\s]+))?",
            r"(pie|bar|line)\s+(?:by|for|of)\s+([a-zA-Z\s]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""


# ── Helper: infer column type from name ──────────────────────────────────────

def _infer_col_type(col_name: str) -> str:
    col_lower = col_name.lower()
    if any(w in col_lower for w in ["salary", "price", "amount", "cost", "revenue",
                                     "total", "pay", "wage", "fee", "income", "expense"]):
        return "currency"
    if any(w in col_lower for w in ["qty", "quantity", "count", "units", "age",
                                     "score", "marks", "number", "hours", "points"]):
        return "number"
    if any(w in col_lower for w in ["date", "dob", "joining", "created", "due", "birth"]):
        return "date"
    if any(w in col_lower for w in ["percent", "%", "rate", "ratio", "achievement"]):
        return "percentage"
    return "text"


# Singleton
intelligence_engine = IntelligenceEngine()


def _sheet_name_from_task(task: dict) -> str:
    """Derive a clean sheet name (max 31 chars) from the task."""
    title = task.get("workbook_title", "") or task.get("user_intent_summary", "Data")
    # Remove words that don't belong in a sheet name
    stop = {"create", "make", "build", "generate", "a", "an", "the", "excel", "sheet", "workbook"}
    words = [w for w in title.split() if w.lower() not in stop]
    name  = " ".join(words[:4]).strip() or "Data"
    # Excel sheet names max 31 chars, no special chars
    safe  = "".join(c for c in name if c.isalnum() or c in " _-")[:31].strip()
    return safe or "Data"
