import os
import json
import requests
import time
import re


class GeminiClient:
    """
    Lightweight Gemini client for planning prompts and action decisions.
    Reads GEMINI_API_KEY from environment or from config.
    """

    def __init__(self, config: dict):
        self.key = os.getenv("GEMINI_API_KEY") or config.get("gemini_api_key")
        self.model = os.getenv("GEMINI_MODEL") or config.get(
            "gemini_model", "gemini-2.5-flash"
        )
        self.endpoint = os.getenv("GEMINI_ENDPOINT") or config.get(
            "gemini_endpoint",
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
        )

        if not self.key:
            raise ValueError("GEMINI_API_KEY not set in environment or config")

    def plan_action(self, prompt: str):
        """
        Send a prompt to Gemini and return the parsed JSON, dict, or raw text.
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.key,
        }
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 2048,
                "topP": 0.8,
                "topK": 40,
            },
        }

        # Retry-once mechanism for transient network or API errors
        data = None
        for attempt in range(2):
            try:
                resp = requests.post(
                    self.endpoint, headers=headers, json=body, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.RequestException as e:
                if attempt == 1:
                    return {"error": f"HTTP error after retry: {e}"}
                print(f"[GeminiClient] Network error, retrying... ({e})")
                time.sleep(1)

        if not data or not data.get("candidates"):
            return {"error": "No candidates", "raw": data}

        try:
            cand = data["candidates"][0]
            parts = cand.get("content", {}).get("parts", [])
            text = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in parts
            ).strip()

            if not text:
                return {"error": "Empty Gemini response", "raw": data}

            parsed = self._extract_json_from_text(text)
            if parsed is not None:
                return parsed

            # Try direct JSON decoding if entire response is JSON
            try:
                return json.loads(text)
            except Exception:
                pass

            # Fallback to structured dict with raw text
            return {"raw_text": text}

        except Exception as e:
            return {"error": f"Parse error: {e}", "raw": data}

    def _extract_json_from_text(self, text: str):
        """
        Extracts the first valid JSON object or array from Gemini text output.
        """
        try:
            # Prefer extracting well-formed JSON blocks
            match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
            if not match:
                return None

            json_str = match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Attempt cleanup for malformed keys or single quotes
                cleaned = json_str.replace("'", '"')
                cleaned = re.sub(r"(\w+):", r'"\1":', cleaned)
                try:
                    return json.loads(cleaned)
                except Exception:
                    return None
        except Exception:
            return None

    def quick_test(self, sample_prompt: str = "Give homepage URL for Linear app"):
        """
        Debug helper to quickly test Gemini connectivity and parsing.
        """
        print(f"[GeminiClient] Sending test prompt: {sample_prompt}")
        result = self.plan_action(sample_prompt)
        print("[GeminiClient] Response:", json.dumps(result, indent=2))
        return result
