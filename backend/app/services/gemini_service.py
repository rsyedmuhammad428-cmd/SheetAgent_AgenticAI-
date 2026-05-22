import google.generativeai as genai
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        if settings.gemini_api_key and settings.gemini_api_key != "missing":
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(
                settings.gemini_model,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )
            self._ready = True
        else:
            self.model = None
            self._ready = False
            logger.warning("GEMINI_API_KEY not set — AI features disabled")

    async def analyze(self, prompt: str, context: str = "") -> str:
        if not self._ready:
            return "AI not configured. Please set GEMINI_API_KEY."
        full = f"{context}\n\n{prompt}" if context else prompt
        try:
            response = self.model.generate_content(full)
            return response.text
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            raise

    async def analyze_json(self, prompt: str, context: str = "") -> dict | list:
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Respond with ONLY valid JSON. "
            "No markdown fences, no backticks, no explanation."
        )
        raw = await self.analyze(json_prompt, context)
        raw = raw.strip()

        # Strip markdown code fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parse error: {e} | raw: {raw[:300]}")
            raise ValueError(f"Gemini returned invalid JSON: {e}")

    async def detect_schema(self, columns: list[str], sample_rows: list[dict]) -> dict:
        prompt = f"""
Analyze this dataset and classify it.

Columns: {columns}
Sample rows: {json.dumps(sample_rows[:5], indent=2)}

Return JSON:
{{
  "schema_type": "invoice|sales_report|inventory|hr_records|student_data|financial|generic",
  "confidence": 0.0-1.0,
  "column_mapping": {{}},
  "suggested_improvements": [],
  "detected_issues": {{"duplicate_rows": 0, "missing_values": {{}}, "inconsistent_formats": []}}
}}
"""
        return await self.analyze_json(prompt)

    async def generate_plan(self, file_name: str, schema_type: str, issues: dict) -> list[str]:
        prompt = f"""
Generate an execution plan for processing this file.
File: {file_name}, Schema: {schema_type}, Issues: {json.dumps(issues)}
Return a JSON array of step strings only.
"""
        result = await self.analyze_json(prompt)
        if isinstance(result, list):
            return result
        return result.get("steps", [f"Process {file_name}", "Clean data", "Generate Excel"])


gemini_service = GeminiService()
