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
        self.gemini_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        
        self.openrouter_key = settings.openrouter_api_key
        self.openrouter_model = settings.openrouter_model

    async def _call_gemini(self, prompt: str, client: httpx.AsyncClient) -> httpx.Response:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        params = {"key": self.gemini_key}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        return await client.post(url, params=params, json=payload, timeout=30.0)

    async def _call_openrouter(self, prompt: str, client: httpx.AsyncClient) -> httpx.Response:
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
        return status_code == 429 or status_code >= 500

    async def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Executes the failover logic:
        Attempt 1: Gemini
        Attempt 2 (if 429/5xx): OpenRouter
        Attempt 3 (if 429/5xx): Gemini
        """
        last_codes = []
        
        async with httpx.AsyncClient() as client:
            # --- Attempt 1: Provider A (Gemini) ---
            attempt = 1
            try:
                resp_a1 = await self._call_gemini(prompt, client)
                last_codes.append(resp_a1.status_code)
                
                if not self._should_retry(resp_a1.status_code):
                    resp_a1.raise_for_status()
                    logger.info("Request successful using Provider A (Gemini) on Attempt 1")
                    return {
                        "status": "success",
                        "text": self._extract_text_gemini(resp_a1.json()),
                        "provider": "Gemini"
                    }
            except httpx.HTTPError as e:
                # Catch network issues and treat them similarly to server errors for failover purposes
                status = getattr(e.response, "status_code", 503) if hasattr(e, "response") else 503
                if len(last_codes) == 0:
                    last_codes.append(status)
                if not self._should_retry(status):
                    # For client errors (400, 401, etc.), we don't failover, we just return the error
                    code_a = last_codes[0] if len(last_codes) > 0 else None
                    return {
                        "status": "error", 
                        "message": f"Gemini Client Error: {e}",
                        "code_a": str(code_a).replace("429", "rate_limited") if code_a == 429 else code_a,
                        "code_b": None
                    }

            # If we reach here, Attempt 1 failed with 429 or 5xx.
            # Pause execution for 2^n seconds (Exponential Backoff, n=1 -> 2 seconds)
            await asyncio.sleep(2 ** attempt)
            
            # --- Attempt 2: Provider B (OpenRouter) ---
            attempt = 2
            try:
                resp_b = await self._call_openrouter(prompt, client)
                last_codes.append(resp_b.status_code)
                
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
                if not self._should_retry(status):
                    code_a = last_codes[0] if len(last_codes) > 0 else None
                    code_b = last_codes[1] if len(last_codes) > 1 else None
                    return {
                        "status": "error", 
                        "message": f"OpenRouter Client Error: {e}",
                        "code_a": str(code_a).replace("429", "rate_limited") if code_a == 429 else code_a,
                        "code_b": code_b
                    }

            # If we reach here, Attempt 2 failed with 429 or 5xx.
            # Pause execution for 2^n seconds (n=2 -> 4 seconds)
            await asyncio.sleep(2 ** attempt)

            # --- Attempt 3: Provider A (Gemini) Once More ---
            attempt = 3
            try:
                resp_a2 = await self._call_gemini(prompt, client)
                # Keep only the last two codes for A and B per constraints, or maybe append A's final code
                last_codes.append(resp_a2.status_code)
                
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
