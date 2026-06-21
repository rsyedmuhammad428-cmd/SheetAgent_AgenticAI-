import asyncio
import httpx
import logging
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class LLMFailoverController:
    """
    Resilient API Middleware Controller
    Provides bidirectional failover between Provider A (Gemini) and Provider B (OpenRouter).
    """

    def __init__(self):
        self.gemini_key = self._clean_setting(settings.gemini_api_key)
        self.gemini_model = self._clean_setting(settings.gemini_model)

        self.openrouter_key = self._clean_setting(settings.openrouter_api_key)
        self.openrouter_model = self._clean_setting(settings.openrouter_model)

    @staticmethod
    def _clean_setting(value: str | None) -> str:
        if value is None:
            return ""
        cleaned = str(value).strip()
        while len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"`", "'", '"'}:
            cleaned = cleaned[1:-1].strip()
        return cleaned

    @staticmethod
    def _is_configured(value: str) -> bool:
        return bool(value and value.lower() not in {"missing", "none", "null", "undefined"})

    async def _call_gemini(self, prompt: str, client: httpx.AsyncClient) -> httpx.Response:
        if not self._is_configured(self.gemini_key):
            raise httpx.HTTPError("Gemini API key is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        params = {"key": self.gemini_key}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        return await client.post(url, params=params, json=payload, timeout=30.0)

    async def _call_openrouter(self, prompt: str, client: httpx.AsyncClient) -> httpx.Response:
        if not self._is_configured(self.openrouter_key):
            raise httpx.HTTPError("OpenRouter API key is not configured")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.openrouter_model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        return await client.post(url, headers=headers, json=payload, timeout=30.0)

    def _extract_text_gemini(self, data: Dict[str, Any]) -> str:
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return ""

    def _extract_text_openrouter(self, data: Dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return ""

    def _should_retry(self, status_code: int) -> bool:
        """
        Return True when the error is worth retrying on the other provider.

        429 = rate-limited    → try other provider
        401 = unauthorized    → invalid/mis-scoped key, try other provider
        403 = forbidden       → Gemini key lacks access to this model (e.g.
                                 gemini-2.5-flash requires billing). Failover
                                 to OpenRouter instead of giving up immediately.
        404 = not found       → wrong model / endpoint / quoted env value
        5xx = server error    → transient, try other provider
        """
        return status_code in (401, 403, 404, 429) or status_code >= 500

    async def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Executes the failover logic:
        Attempt 1: Gemini
        Attempt 2 (if 429/5xx): OpenRouter
        Attempt 3 (if 429/5xx): Gemini
        """
        last_codes = []

        gemini_enabled = self._is_configured(self.gemini_key) and self._is_configured(self.gemini_model)
        openrouter_enabled = self._is_configured(self.openrouter_key) and self._is_configured(self.openrouter_model)

        if not gemini_enabled and not openrouter_enabled:
            return {
                "status": "error",
                "message": "No LLM provider is configured. Set GEMINI_API_KEY or OPENROUTER_API_KEY.",
                "code_a": None,
                "code_b": None,
            }

        logger.info(
            "LLM failover start | gemini_enabled=%s | openrouter_enabled=%s",
            gemini_enabled,
            openrouter_enabled,
        )
        
        async with httpx.AsyncClient() as client:
            # --- Attempt 1: Provider A (Gemini) ---
            attempt = 1
            if gemini_enabled:
                try:
                    resp_a1 = await self._call_gemini(prompt, client)
                    last_codes.append(resp_a1.status_code)
                    logger.info("LLM attempt 1 Gemini status=%s", resp_a1.status_code)

                    if not self._should_retry(resp_a1.status_code):
                        resp_a1.raise_for_status()
                        logger.info("Request successful using Provider A (Gemini) on Attempt 1")
                        return {
                            "status": "success",
                            "text": self._extract_text_gemini(resp_a1.json()),
                            "provider": "Gemini"
                        }
                except httpx.HTTPError as e:
                    status = getattr(e.response, "status_code", 503) if hasattr(e, "response") else 503
                    if len(last_codes) == 0:
                        last_codes.append(status)
                    logger.warning("LLM attempt 1 Gemini failed status=%s", status)
                    if not self._should_retry(status) and not openrouter_enabled:
                        code_a = last_codes[0] if len(last_codes) > 0 else None
                        return {
                            "status": "error",
                            "message": f"Gemini Client Error: {e}",
                            "code_a": str(code_a).replace("429", "rate_limited") if code_a == 429 else code_a,
                            "code_b": None
                        }
            else:
                last_codes.append(None)

            if openrouter_enabled:
                await asyncio.sleep(2 ** attempt)
            
                # --- Attempt 2: Provider B (OpenRouter) ---
                attempt = 2
                try:
                    resp_b = await self._call_openrouter(prompt, client)
                    last_codes.append(resp_b.status_code)
                    logger.info("LLM attempt 2 OpenRouter status=%s", resp_b.status_code)

                    if not self._should_retry(resp_b.status_code):
                        resp_b.raise_for_status()
                        logger.info("Request successful using Provider B (OpenRouter) on Attempt 2")
                        return {
                            "status": "success",
                            "text": self._extract_text_openrouter(resp_b.json()),
                            "provider": "OpenRouter"
                        }
                except httpx.HTTPError as e:
                    status = getattr(e.response, "status_code", 503) if hasattr(e, "response") else 503
                    if len(last_codes) == 1:
                        last_codes.append(status)
                    logger.warning("LLM attempt 2 OpenRouter failed status=%s", status)
                    if not self._should_retry(status):
                        code_a = last_codes[0] if len(last_codes) > 0 else None
                        code_b = last_codes[1] if len(last_codes) > 1 else None
                        return {
                            "status": "error",
                            "message": f"OpenRouter Client Error: {e}",
                            "code_a": str(code_a).replace("429", "rate_limited") if code_a == 429 else code_a,
                            "code_b": code_b
                        }
            else:
                if len(last_codes) == 1:
                    last_codes.append(None)

            if gemini_enabled:
                await asyncio.sleep(2 ** attempt)

                # --- Attempt 3: Provider A (Gemini) Once More ---
                attempt = 3
                try:
                    resp_a2 = await self._call_gemini(prompt, client)
                    last_codes.append(resp_a2.status_code)
                    logger.info("LLM attempt 3 Gemini status=%s", resp_a2.status_code)

                    if not self._should_retry(resp_a2.status_code):
                        resp_a2.raise_for_status()
                        logger.info("Request successful using Provider A (Gemini) on Attempt 3")
                        return {
                            "status": "success",
                            "text": self._extract_text_gemini(resp_a2.json()),
                            "provider": "Gemini"
                        }
                except httpx.HTTPError as e:
                    status = getattr(e.response, "status_code", 503) if hasattr(e, "response") else 503
                    if len(last_codes) == 2:
                        last_codes.append(status)
                    logger.warning("LLM attempt 3 Gemini failed status=%s", status)
                
            # If all 3 attempts fail or we get 429/5xx on the 3rd attempt, return standardized JSON error
            code_a = last_codes[0] if len(last_codes) > 0 else None
            code_b = last_codes[1] if len(last_codes) > 1 else None
            
            logger.error("All providers exhausted. No sensitive keys logged.")
            
            error_msg = "All providers exhausted"
            if code_b == 404:
                error_msg = "OpenRouter returned 404 (Model Not Found). Please check OPENROUTER_MODEL."
            elif code_b == 401:
                error_msg = "OpenRouter returned 401 (Unauthorized). Please check OPENROUTER_API_KEY."

            return {
                "status": "error", 
                "message": error_msg, 
                "code_a": str(code_a).replace("429", "rate_limited") if code_a == 429 else code_a,
                "code_b": code_b
            }

# Instantiable Controller
llm_controller = LLMFailoverController()
