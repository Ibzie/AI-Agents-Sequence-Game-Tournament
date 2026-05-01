import os
import time

from .base import BaseProvider, CompletionResult


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
    ) -> CompletionResult:
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

        start = time.perf_counter()
        response = client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start

        content = response.choices[0].message.content
        prompt_tokens = None
        completion_tokens = None
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens

        return CompletionResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_seconds=elapsed,
        )