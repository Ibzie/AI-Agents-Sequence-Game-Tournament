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
class PlayerStats:
    total_moves: int = 0
    total_duration_seconds: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    @property
    def avg_move_duration_seconds(self) -> float:
        return self.total_duration_seconds / self.total_moves if self.total_moves > 0 else 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def avg_tokens_per_move(self) -> float:
        return self.total_tokens / self.total_moves if self.total_moves > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_moves": self.total_moves,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "avg_move_duration_seconds": round(self.avg_move_duration_seconds, 2),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "avg_tokens_per_move": round(self.avg_tokens_per_move, 1),
        }

    @classmethod
    def from_dict(cls, d: dict) -> PlayerStats:
        return cls(
            total_moves=d.get("total_moves", 0),
            total_duration_seconds=d.get("total_duration_seconds", 0.0),
            total_prompt_tokens=d.get("total_prompt_tokens", 0),
            total_completion_tokens=d.get("total_completion_tokens", 0),
        )


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
    move_duration_seconds: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

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
        if self.move_duration_seconds is not None:
            d["move_duration_seconds"] = self.move_duration_seconds
        if self.prompt_tokens is not None:
            d["prompt_tokens"] = self.prompt_tokens
        if self.completion_tokens is not None:
            d["completion_tokens"] = self.completion_tokens
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
            move_duration_seconds=d.get("move_duration_seconds"),
            prompt_tokens=d.get("prompt_tokens"),
            completion_tokens=d.get("completion_tokens"),
        )


@dataclass
class GameLog:
    game_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    players: list[PlayerInfo] = field(default_factory=list)
    winner: Optional[str] = None
    events: list[GameEvent] = field(default_factory=list)
    player_stats: dict[str, PlayerStats] = field(default_factory=dict)

    def add_event(self, event: GameEvent):
        self.events.append(event)

    def compute_stats(self):
        stats: dict[str, PlayerStats] = {}
        for event in self.events:
            if event.type != "move" or event.move_duration_seconds is None:
                continue
            pid = event.player
            if pid not in stats:
                stats[pid] = PlayerStats()
            s = stats[pid]
            s.total_moves += 1
            s.total_duration_seconds += event.move_duration_seconds or 0.0
            s.total_prompt_tokens += event.prompt_tokens or 0
            s.total_completion_tokens += event.completion_tokens or 0
        self.player_stats = stats

    def to_dict(self) -> dict:
        if not self.player_stats:
            self.compute_stats()
        return {
            "game_id": self.game_id,
            "created_at": self.created_at,
            "players": [
                {"id": p.id, "model": p.model, "provider": p.provider, "chip": p.chip}
                for p in self.players
            ],
            "winner": self.winner,
            "events": [e.to_dict() for e in self.events],
            "player_stats": {
                pid: s.to_dict() for pid, s in self.player_stats.items()
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> GameLog:
        players = [PlayerInfo(**p) for p in d.get("players", [])]
        events = [GameEvent.from_dict(e) for e in d.get("events", [])]
        player_stats = {
            pid: PlayerStats.from_dict(s) for pid, s in d.get("player_stats", {}).items()
        }
        return cls(
            game_id=d["game_id"],
            created_at=d.get("created_at", ""),
            players=players,
            winner=d.get("winner"),
            events=events,
            player_stats=player_stats,
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
                player_stats = data.get("player_stats", {})
                games.append({
                    "game_id": data["game_id"],
                    "created_at": data.get("created_at", ""),
                    "winner": data.get("winner"),
                    "players": data.get("players", []),
                    "event_count": len(data.get("events", [])),
                    "player_stats": player_stats,
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