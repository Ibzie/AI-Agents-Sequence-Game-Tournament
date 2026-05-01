import logging
import random
import time
from dataclasses import dataclass

from Game.sequence.state import GameState
from Game.sequence.random_agent import random_agent

from .base_agent import BaseAgent
from .providers.base import BaseProvider, CompletionResult
from .prompt import build_messages, build_retry_messages
from .parser import parse_move_index

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


@dataclass
class MoveMetrics:
    duration_seconds: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    retries: int = 0


class LLMAgent(BaseAgent):
    def __init__(
        self,
        provider: BaseProvider,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        player_id: str = "ai",
    ):
        super().__init__()
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.player_id = player_id
        self.last_metrics: MoveMetrics | None = None

    def choose_move(self, state: GameState, legal_moves: list) -> dict:
        messages = build_messages(state, legal_moves)
        start_time = time.perf_counter()
        total_prompt_tokens = 0
        total_completion_tokens = 0
        token_counts_valid = True
        retries = 0

        for attempt in range(MAX_RETRIES):
            logger.info(f"[{self.player_id}] Attempt {attempt + 1}/{MAX_RETRIES}")
            logger.debug(f"[{self.player_id}] Prompt:\n{messages[-1]['content'][:500]}...")

            try:
                result: CompletionResult = self.provider.complete(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                raw_response = result.content
            except Exception as e:
                logger.error(f"[{self.player_id}] Provider error: {e}")
                retries += 1
                continue

            if result.prompt_tokens is not None:
                total_prompt_tokens += result.prompt_tokens
            else:
                token_counts_valid = False
            if result.completion_tokens is not None:
                total_completion_tokens += result.completion_tokens
            else:
                token_counts_valid = False

            logger.info(f"[{self.player_id}] LLM response: {raw_response[:300]}")
            self.last_response = raw_response

            thinking = getattr(self.provider, 'last_thinking', None)
            if thinking:
                self.last_response = f"<thinking>\n{thinking}\n</thinking>\n{raw_response}"

            move = parse_move_index(raw_response, legal_moves)
            if move is not None:
                logger.info(
                    f"[{self.player_id}] Parsed move: {move['type']} card={move['card']} "
                    f"pos={move.get('position')}"
                )
                elapsed = time.perf_counter() - start_time
                self.last_metrics = MoveMetrics(
                    duration_seconds=elapsed,
                    prompt_tokens=total_prompt_tokens if token_counts_valid else None,
                    completion_tokens=total_completion_tokens if token_counts_valid else None,
                    retries=retries,
                )
                return move

            logger.warning(f"[{self.player_id}] Failed to parse move, retrying with feedback...")
            retries += 1
            messages = build_retry_messages(
                messages, raw_response,
                f"Could not extract a valid move index (0-{len(legal_moves)-1}) from your response.",
                legal_moves,
            )

        logger.warning(f"[{self.player_id}] All retries exhausted. Falling back to random move.")
        elapsed = time.perf_counter() - start_time
        self.last_response = "(random fallback)"
        self.last_metrics = MoveMetrics(
            duration_seconds=elapsed,
            prompt_tokens=total_prompt_tokens if token_counts_valid else None,
            completion_tokens=total_completion_tokens if token_counts_valid else None,
            retries=MAX_RETRIES,
        )
        return random_agent(legal_moves)