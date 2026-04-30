from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from Game.sequence.state import init_game, GameState
from Game.sequence.game import apply_move, get_moves_for_current_player, is_game_over
from Game.sequence.random_agent import random_agent

from AI.game_log import GameEvent, GameLog, PlayerInfo, _snapshot_state

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    p1_provider: str = "ollama"
    p1_model: str = "llama3"
    p1_id: str = "player1"
    p2_provider: str = "ollama"
    p2_model: str = "llama3"
    p2_id: str = "player2"
    delay_ms: int = 500
    max_turns: int = 500
    ollama_host: str = "http://localhost:11434"


def _create_agent(config_item: dict):
    from AI.providers import get_provider
    from AI.llm_agent import LLMAgent

    provider = get_provider(config_item["provider"], **config_item.get("provider_kwargs", {}))
    return LLMAgent(
        provider=provider,
        model=config_item["model"],
        player_id=config_item["id"],
    )


def _run_sync(config: GameConfig, callback: Optional[Callable[[dict], None]] = None) -> GameLog:
    p1_info = PlayerInfo(id=config.p1_id, model=config.p1_model, provider=config.p1_provider, chip="blue")
    p2_info = PlayerInfo(id=config.p2_id, model=config.p2_model, provider=config.p2_provider, chip="green")

    game_log = GameLog(players=[p1_info, p2_info])

    player_ids = [config.p1_id, config.p2_id]
    chips = {config.p1_id: "blue", config.p2_id: "green"}
    state = init_game(player_ids=player_ids, chips=chips)

    agent_map = {}
    for info, cfg_key in [(p1_info, "p1"), (p2_info, "p2")]:
        try:
            provider_kwargs = {}
            if info.provider == "ollama":
                provider_kwargs["host"] = config.ollama_host
            agent = _create_agent({
                "provider": info.provider,
                "model": info.model,
                "id": info.id,
                "provider_kwargs": provider_kwargs,
            })
            agent_map[info.id] = agent
        except Exception as e:
            logger.error(f"Failed to create agent for {info.id}: {e}")
            raise

    deal_event = GameEvent(
        turn=0,
        player="dealer",
        type="deal",
        hand_before=None,
        hand_after={pid: list(state.hands[pid]) for pid in player_ids},
        snapshot=_snapshot_state(state),
    )
    game_log.add_event(deal_event)

    if callback:
        callback(deal_event.to_dict())

    while not is_game_over(state) and state.turn_number < config.max_turns:
        current = state.current_player
        moves = get_moves_for_current_player(state)

        if not moves:
            logger.warning(f"No legal moves for {current}. Game ends in draw.")
            event = GameEvent(
                turn=state.turn_number,
                player=current,
                type="draw",
                move=None,
                snapshot=_snapshot_state(state),
            )
            game_log.add_event(event)
            if callback:
                callback(event.to_dict())
            break

        hand_before = list(state.hands[current])

        agent = agent_map[current]
        move = agent.choose_move(state, moves)

        move_serializable = {
            "type": move["type"],
            "card": move["card"],
            "position": list(move["position"]) if move.get("position") else None,
        }

        event = GameEvent(
            turn=state.turn_number,
            player=current,
            type="move",
            move=move_serializable,
            hand_before=hand_before,
            snapshot=_snapshot_state(state),
        )
        game_log.add_event(event)
        if callback:
            callback(event.to_dict())

        state = apply_move(state, move)

        event_after = GameEvent(
            turn=state.turn_number,
            player=current,
            type="move_after",
            move=move_serializable,
            hand_after=list(state.hands[current]),
            snapshot=_snapshot_state(state),
        )
        game_log.add_event(event_after)
        if callback:
            callback(event_after.to_dict())

    if state.winner:
        game_log.winner = state.winner
    end_event = GameEvent(
        turn=state.turn_number,
        player=state.winner or "none",
        type="game_over",
        move={"winner": state.winner, "reason": "sequences" if state.winner else "draw"},
        snapshot=_snapshot_state(state),
    )
    game_log.add_event(end_event)
    if callback:
        callback(end_event.to_dict())

    return game_log


def run_game_streaming(config: GameConfig, callback: Optional[Callable[[dict], None]] = None) -> GameLog:
    return _run_sync(config, callback)


def run_game_in_thread(config: GameConfig, result_queue: queue.Queue, callback: Optional[Callable[[dict], None]] = None):
    try:
        game_log = _run_sync(config, callback)
        result_queue.put(("done", game_log))
    except Exception as e:
        logger.exception(f"Game thread error: {e}")
        result_queue.put(("error", str(e)))