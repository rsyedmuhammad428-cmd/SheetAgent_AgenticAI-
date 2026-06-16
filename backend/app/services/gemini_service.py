"""
Phase 6 — Gemini Service
Robust JSON extraction with retry logic.
Handles all response formats Gemini returns.
"""
import json
import re
import logging
import asyncio
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


from app.services.llm_failover import llm_controller

class GeminiService:
    def __init__(self):
        self._ready = True

    @property
    def ready(self) -> bool:
        return self._ready

    async def analyze(self, prompt: str, context: str = "") -> str:
        full = f"{context}\n\n{prompt}" if context else prompt
        try:
            result = await llm_controller.generate(full)
            if result.get("status") == "success":
                return result.get("text", "")
            else:
                raise Exception(f"Failover error: {result}")
        except Exception as e:
            logger.error(f"Gemini analyze: {e}")
            raise

    async def analyze_json(self, prompt: str, context: str = "") -> dict | list:
        """
        Call Gemini and extract valid JSON from response.
        Tries 3 times with increasing instruction clarity.
        """
        attempts = [
            prompt + "\n\nCRITICAL: Return ONLY valid JSON. Start with { or [. No markdown. No explanation.",
            "Return ONLY a JSON object or array. Start immediately with { or [.\n\n" + prompt,
            prompt + "\n\nJSON ONLY. No text before or after. No ```json blocks.",
        ]

        last_error = None
        for i, attempt_prompt in enumerate(attempts):
            try:
                raw = await self.analyze(attempt_prompt, context)
                result = self._extract_json(raw)
                if i > 0:
                    logger.info(f"JSON succeeded on attempt {i+1}")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"JSON attempt {i+1}/3 failed: {e}")
                if i < 2:
                    await asyncio.sleep(0.5)

        raise ValueError(f"JSON extraction failed after 3 attempts: {last_error}")

    def _extract_json(self, raw: str) -> dict | list:
        """Extract JSON from any Gemini response format."""
        if not raw or not raw.strip():
            raise ValueError("Empty response")

        text = raw.strip()

        # Try 1: Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try 2: Extract from ```json...``` block
        m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try 3: Extract from ```...``` block
        m = re.search(r'```\s*([\s\S]+?)\s*```', text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try 4: Find first complete JSON object or array
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            idx = text.find(start_char)
            if idx == -1:
                continue
            depth = 0
            end_idx = -1
            in_string = False
            escape_next = False
            for j in range(idx, len(text)):
                ch = text[j]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if ch == start_char:
                        depth += 1
                    elif ch == end_char:
                        depth -= 1
                    if depth == 0:
                        end_idx = j
                        break
            if end_idx != -1:
                candidate = text[idx:end_idx + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Try cleaning common issues
                    cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
                    cleaned = re.sub(r'//[^\n]*', '', cleaned)
                    try:
                        return json.loads(cleaned)
                    except json.JSONDecodeError:
                        pass

        raise ValueError(f"No valid JSON found in: {text[:300]}")

    async def detect_schema(self, columns: list, sample_rows: list) -> dict:
        prompt = f"""Classify this dataset.
Columns: {columns}
Sample: {json.dumps(sample_rows[:3], default=str)}
Return JSON: {{"schema_type":"invoice|sales_report|inventory|hr_records|student_data|financial|generic","confidence":0.9}}"""
        try:
            return await self.analyze_json(prompt)
        except Exception:
            return {"schema_type": "generic", "confidence": 0.5}

    async def generate_plan(self, file_name: str, schema_type: str, issues: dict) -> list:
        prompt = f"""Generate 5 processing steps for: {file_name} (schema: {schema_type})
Return JSON array of 5 step strings."""
        try:
            r = await self.analyze_json(prompt)
            return r if isinstance(r, list) else r.get("steps", [])
        except Exception:
            return [
                f"Analyze {file_name}",
                "Extract structured data",
                "Clean and normalize",
                "Generate Excel workbook",
                "Apply formatting and formulas",
            ]


gemini_service = GeminiService()
