import os
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )

    def complete(
        self,
        messages: list[dict],
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        system_text = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                user_messages.append(msg)

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_text:
            kwargs["system"] = system_text

        response = client.messages.create(**kwargs)
        return response.content[0].text