"""
LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import requests


class LLMProviderError(RuntimeError):
    """Provider error."""


class BaseLLMProvider(ABC):
    @abstractmethod
    def analyze(self, user_text: str) -> Dict[str, Any]:
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
    """
    Ollama provider using /api/generate for deterministic JSON output.
    """

    def __init__(self, base_url: str, model: str, timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def analyze(self, user_text: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": user_text,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_s
            )
            response.raise_for_status()
        except Exception as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Invalid JSON from Ollama") from exc

        # Ollama returns {"response": "..."} for /api/generate
        content = data.get("response", "")
        if not content:
            raise LLMProviderError("Empty Ollama response")

        # Best-effort JSON parse with fallback extraction
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON block from text
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError as exc:
                    raise LLMProviderError("Ollama response is not JSON") from exc
            raise LLMProviderError("Ollama response is not JSON")


class CloudFallbackProvider(BaseLLMProvider):
    """
    Optional cloud fallback stub.
    This preserves compatibility if you later plug in OpenAI or other APIs.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def analyze(self, user_text: str) -> Dict[str, Any]:
        if not self.enabled:
            raise LLMProviderError("Cloud fallback disabled")
        raise LLMProviderError("Cloud fallback not configured")
