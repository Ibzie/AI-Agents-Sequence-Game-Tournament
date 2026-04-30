import logging
import httpx
from .base import BaseProvider

logger = logging.getLogger(__name__)

THINKING_MODEL_PREFIXES = ("qwen3", "qwq", "deepseek-r1")


class OllamaProvider(BaseProvider):
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")
        self.last_thinking = None

    def _is_thinking_model(self, model: str) -> bool:
        base = model.split(":")[0] if ":" in model else model
        return any(base.startswith(p) for p in THINKING_MODEL_PREFIXES)

    def complete(
        self,
        messages: list[dict],
        model: str = "llama3",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        self.last_thinking = None

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if self._is_thinking_model(model):
            payload["think"] = True

        response = httpx.post(
            f"{self.host}/api/chat",
            json=payload,
            timeout=180.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"]
        thinking = data["message"].get("thinking", "")

        if thinking and thinking.strip():
            self.last_thinking = thinking

        if not content or not content.strip():
            if thinking and thinking.strip():
                logger.info(f"Ollama returned empty content but has thinking ({len(thinking)} chars); extracting from thinking")
                import re
                json_match = re.search(r'\{[^{}]*"move_index"\s*:\s*\d+[^{}]*\}', thinking)
                if json_match:
                    content = json_match.group(0)
                    logger.info(f"Extracted JSON from thinking: {content}")
                else:
                    content = thinking

        return content