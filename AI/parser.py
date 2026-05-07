import json
import re
import logging

from Game.sequence.board import BOARD_LAYOUT

logger = logging.getLogger(__name__)


def parse_move_index(response: str, legal_moves: list) -> dict | None:
    text = response.strip()

    try:
        data = json.loads(text)
        move = _parse_data(data, legal_moves)
        if move is not None:
            return move
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^{}]*"move_index"\s*:\s*(\d+)[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            move = _parse_data(data, legal_moves)
            if move is not None:
                return move
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: try to find a JSON object with position coordinates for wild jack
    pos_match = re.search(
        r'\{[^{}]*"move_index"\s*:\s*(\d+)[^{}]*"position"\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\][^{}]*\}',
        text,
    )
    if pos_match:
        try:
            idx = int(pos_match.group(1))
            row = int(pos_match.group(2))
            col = int(pos_match.group(3))
            move = _resolve_wild_jack(idx, (row, col), legal_moves)
            if move is not None:
                return move
        except (ValueError, IndexError):
            pass

    logger.warning(f"Could not parse any move index from response: {text[:200]}")
    return None


def _parse_data(data: dict, legal_moves: list) -> dict | None:
    if not isinstance(data, dict) or "move_index" not in data:
        return None

    idx = data["move_index"]
    if not isinstance(idx, int) or not (0 <= idx < len(legal_moves)):
        logger.warning(f"move_index {idx} out of range (0-{len(legal_moves)-1})")
        return None

    # If position coords are provided, this is a wild jack placement
    if "position" in data:
        pos = data["position"]
        if isinstance(pos, list) and len(pos) == 2:
            row, col = int(pos[0]), int(pos[1])
            return _resolve_wild_jack(idx, (row, col), legal_moves)

    return legal_moves[idx]


def _resolve_wild_jack(move_index: int, target_pos: tuple, legal_moves: list) -> dict | None:
    if move_index < 0 or move_index >= len(legal_moves):
        return None

    base_move = legal_moves[move_index]
    if base_move["type"] != "two_eyed_jack":
        # Not a wild jack — just use the indexed move
        return base_move

    # Validate the target position is empty and not a corner
    from Game.sequence.state import GameState
    if target_pos in {(0, 0), (0, 9), (9, 0), (9, 9)}:
        logger.warning(f"Wild jack position {target_pos} is a corner — not allowed")
        return None

    if BOARD_LAYOUT.get(target_pos) == "XX" or BOARD_LAYOUT.get(target_pos) is None:
        # Invalid position on board
        return None

    # Check if position is actually in the legal moves for this wild jack
    for move in legal_moves:
        if move["type"] == "two_eyed_jack" and move["position"] == target_pos and move["card"] == base_move["card"]:
            logger.info(f"Resolved wild jack via coordinates: card={base_move['card']} at {target_pos}")
            return move

    # Position is empty on the board — create a valid move dict for it
    # We need to verify the position is actually empty. We can't check board state here
    # without access to it, so we trust the LLM's coordinates and construct the move.
    # The game engine will validate legality.
    logger.info(f"Constructing wild jack move: card={base_move['card']} at {target_pos}")
    return {
        "card": base_move["card"],
        "type": "two_eyed_jack",
        "position": target_pos,
    }