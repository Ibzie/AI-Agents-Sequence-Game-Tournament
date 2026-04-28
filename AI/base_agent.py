from abc import ABC, abstractmethod
from Game.sequence.state import GameState


class BaseAgent(ABC):
    @abstractmethod
    def choose_move(self, state: GameState, legal_moves: list) -> dict:
        raise NotImplementedError