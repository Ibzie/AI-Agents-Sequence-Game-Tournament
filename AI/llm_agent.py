import logging
import random

from Game.sequence.state import GameState
from Game.sequence.random_agent import random_agent

from .base_agent import BaseAgent
from .providers.base import BaseProvider
from .prompt import build_messages, build_retry_messages
from .parser import parse_move_index

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


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

    def choose_move(self, state: GameState, legal_moves: list) -> dict:
        messages = build_messages(state, legal_moves)

        for attempt in range(MAX_RETRIES):
            logger.info(f"[{self.player_id}] Attempt {attempt + 1}/{MAX_RETRIES}")
            logger.debug(f"[{self.player_id}] Prompt:\n{messages[-1]['content'][:500]}...")

            try:
                raw_response = self.provider.complete(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except Exception as e:
                logger.error(f"[{self.player_id}] Provider error: {e}")
                continue

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
                return move

            logger.warning(f"[{self.player_id}] Failed to parse move, retrying with feedback...")
            messages = build_retry_messages(
                messages, raw_response,
                f"Could not extract a valid move index (0-{len(legal_moves)-1}) from your response.",
                legal_moves,
            )

        logger.warning(f"[{self.player_id}] All retries exhausted. Falling back to random move.")
        self.last_response = "(random fallback)"
        return random_agent(legal_moves)