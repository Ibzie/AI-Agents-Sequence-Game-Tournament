import os
from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key."
            )
        self.base_url = base_url

    def complete(
        self,
        messages: list[dict],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        import openai

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.base_url:
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            client = openai.OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content