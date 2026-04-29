from dataclasses import dataclass, field
from typing import Optional
import json

@dataclass
class GameState:
    board: dict                      # (row,col) -> chip string or None
    hands: dict                      # player_id -> list of card strings
    deck: list                       # remaining draw pile
    discard_pile: list               # shared discard pile
    current_player: str              # player_id whose turn it is
    players: list                    # ordered list of player_ids
    chips: dict                      # player_id -> chip color string
    sequences: dict                  # player_id -> sequence count
    locked_positions: set            # positions locked by completed sequences
    turn_number: int = 0
    winner: Optional[str] = None
    move_history: list = field(default_factory=list)  # [(player_id, move_dict), ...]

    def to_json(self):
        return json.dumps({
            'board': {f"{r},{c}": v for (r,c), v in self.board.items()},
            'hands': self.hands,
            'deck_size': len(self.deck),
            'discard_size': len(self.discard_pile),
            'current_player': self.current_player,
            'players': self.players,
            'chips': self.chips,
            'sequences': self.sequences,
            'locked_positions': [list(p) for p in self.locked_positions],
            'turn_number': self.turn_number,
            'winner': self.winner,
        }, indent=2)

def init_game(player_ids, chips):
    """Bootstrap a fresh GameState.
    player_ids: list of player id strings e.g. ['player1', 'player2']
    chips: dict of player_id -> chip color e.g. {'player1': 'blue', 'player2': 'green'}
    """
    from .deck import build_deck, deal

    deck = build_deck()
    hands_list, deck = deal(deck, num_players=len(player_ids))
    hands = {pid: hand for pid, hand in zip(player_ids, hands_list)}

    board = {
        (row, col): None
        for row in range(10)
        for col in range(10)
    }

    return GameState(
        board=board,
        hands=hands,
        deck=deck,
        discard_pile=[],
        current_player=player_ids[0],
        players=player_ids,
        chips=chips,
        sequences={pid: 0 for pid in player_ids},
        locked_positions=set(),
        turn_number=0,
        winner=None,
    )