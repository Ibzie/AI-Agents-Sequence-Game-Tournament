import httpx
from .base import BaseProvider


class OllamaProvider(BaseProvider):
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")

    def complete(
        self,
        messages: list[dict],
        model: str = "llama3",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        response = httpx.post(
            f"{self.host}/api/chat",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]