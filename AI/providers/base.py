from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        raise NotImplementedError