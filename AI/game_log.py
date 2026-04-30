from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

LOGS_DIR = Path(__file__).resolve().parent.parent / "visualizer" / "logs"


def _snapshot_state(state) -> dict:
    board = {}
    for (r, c), chip in state.board.items():
        if chip is not None:
            board[f"{r},{c}"] = chip
    hands = {pid: list(cards) for pid, cards in state.hands.items()}
    return {
        "current_player": state.current_player,
        "board": board,
        "hands": hands,
        "sequences": dict(state.sequences),
        "deck_size": len(state.deck),
        "discard_size": len(state.discard_pile),
        "turn_number": state.turn_number,
        "winner": state.winner,
        "players": list(state.players),
        "chips": dict(state.chips),
    }


@dataclass
class PlayerInfo:
    id: str
    model: str
    provider: str
    chip: str


@dataclass
class GameEvent:
    turn: int
    player: str
    type: str
    move: Optional[dict] = None
    hand_before: Optional[list] = None
    hand_after: Optional[Union[list, dict]] = None
    llm_response: Optional[str] = None
    snapshot: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {"turn": self.turn, "player": self.player, "type": self.type}
        if self.move is not None:
            d["move"] = self.move
        if self.hand_before is not None:
            d["hand_before"] = self.hand_before
        if self.hand_after is not None:
            d["hand_after"] = self.hand_after
        if self.llm_response is not None:
            d["llm_response"] = self.llm_response
        if self.snapshot is not None:
            d["snapshot"] = self.snapshot
        return d

    @classmethod
    def from_dict(cls, d: dict) -> GameEvent:
        return cls(
            turn=d["turn"],
            player=d["player"],
            type=d["type"],
            move=d.get("move"),
            hand_before=d.get("hand_before"),
            hand_after=d.get("hand_after"),
            llm_response=d.get("llm_response"),
            snapshot=d.get("snapshot"),
        )


@dataclass
class GameLog:
    game_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    players: list[PlayerInfo] = field(default_factory=list)
    winner: Optional[str] = None
    events: list[GameEvent] = field(default_factory=list)

    def add_event(self, event: GameEvent):
        self.events.append(event)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "created_at": self.created_at,
            "players": [
                {"id": p.id, "model": p.model, "provider": p.provider, "chip": p.chip}
                for p in self.players
            ],
            "winner": self.winner,
            "events": [e.to_dict() for e in self.events],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> GameLog:
        players = [PlayerInfo(**p) for p in d.get("players", [])]
        events = [GameEvent.from_dict(e) for e in d.get("events", [])]
        return cls(
            game_id=d["game_id"],
            created_at=d.get("created_at", ""),
            players=players,
            winner=d.get("winner"),
            events=events,
        )

    @classmethod
    def from_json(cls, text: str) -> GameLog:
        return cls.from_dict(json.loads(text))


class GameStore:
    def __init__(self, logs_dir: Optional[Path] = None):
        self.logs_dir = logs_dir or LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, game_log: GameLog) -> Path:
        path = self.logs_dir / f"{game_log.game_id}.json"
        path.write_text(game_log.to_json())
        return path

    def load(self, game_id: str) -> GameLog:
        path = self.logs_dir / f"{game_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Game log {game_id} not found")
        return GameLog.from_json(path.read_text())

    def list_games(self) -> list[dict]:
        games = []
        for path in sorted(self.logs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text())
                games.append({
                    "game_id": data["game_id"],
                    "created_at": data.get("created_at", ""),
                    "winner": data.get("winner"),
                    "players": data.get("players", []),
                    "event_count": len(data.get("events", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return games

    def delete(self, game_id: str) -> bool:
        path = self.logs_dir / f"{game_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False