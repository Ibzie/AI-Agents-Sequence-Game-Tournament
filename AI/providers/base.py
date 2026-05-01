from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionResult:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_seconds: float = 0.0


class BaseProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> CompletionResult:
        raise NotImplementedError