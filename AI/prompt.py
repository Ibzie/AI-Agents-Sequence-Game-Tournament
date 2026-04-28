from Game.sequence.board import BOARD_LAYOUT
from Game.sequence.state import GameState

SYSTEM_PROMPT = """You are an expert Sequence board game player. You will receive the current game state and a numbered list of legal moves. Your goal is to win by completing 2 sequences (5 chips in a row: horizontal, vertical, or diagonal) before your opponent.

Board corners (marked XX) are wild — they count toward any sequence for any player.

Card types:
- Regular cards: Place your chip on one of the card's two board positions.
- Two-eyed jacks (JH, JD): Wild — place your chip on any empty non-corner space.
- One-eyed jacks (JS, JC): Anti-wild — remove one opponent chip (not from a completed sequence).
- Dead card: If both positions for a card are occupied, it must be discarded and you draw a replacement.

You MUST respond with ONLY a JSON object in this exact format:
{"move_index": <integer>}

Where <integer> is the index number of the move you choose from the legal moves list (0-based). Do not include any other text."""


def render_board(state: GameState) -> str:
    lines = []
    header = "     " + " ".join(f"{c:>4}" for c in range(10))
    lines.append(header)
    lines.append("    " + "-" * 45)
    for row in range(10):
        chip_strs = []
        for col in range(10):
            pos = (row, col)
            chip = state.board.get(pos)
            card = BOARD_LAYOUT[pos]
            if chip is not None:
                chip_strs.append(f"{chip[0].upper()}@{card:>3}")
            elif card == "XX":
                chip_strs.append("  XX ")
            else:
                chip_strs.append(f"  {card:>3} ")
        lines.append(f" {row:>2} |" + "|".join(chip_strs) + "|")
    lines.append("    " + "-" * 45)
    legend = "Chip colors:"
    for pid, chip_color in state.chips.items():
        legend += f" {pid}={chip_color[0].upper()}"
    lines.append(legend)
    return "\n".join(lines)


def render_hand(state: GameState) -> str:
    hand = state.hands[state.current_player]
    cards = ", ".join(hand)
    return f"Your hand ({len(hand)} cards): {cards}"


def render_sequences(state: GameState) -> str:
    parts = []
    for pid in state.players:
        parts.append(f"  {pid}: {state.sequences[pid]} sequences")
    return "Sequences:\n" + "\n".join(parts)


def render_legal_moves(legal_moves: list) -> str:
    lines = []
    for i, move in enumerate(legal_moves):
        if move["type"] == "dead_card":
            lines.append(f"  [{i}] Discard dead card {move['card']}")
        elif move["type"] == "place":
            pos = move["position"]
            lines.append(f"  [{i}] Play {move['card']} at position ({pos[0]},{pos[1]})")
        elif move["type"] == "two_eyed_jack":
            pos = move["position"]
            lines.append(f"  [{i}] Play two-eyed jack {move['card']} (wild) at ({pos[0]},{pos[1]})")
        elif move["type"] == "one_eyed_jack":
            pos = move["position"]
            lines.append(f"  [{i}] Play one-eyed jack {move['card']} — remove opponent at ({pos[0]},{pos[1]})")
    return "\n".join(lines)


def build_messages(state: GameState, legal_moves: list) -> list[dict]:
    board_view = render_board(state)
    hand_view = render_hand(state)
    seq_view = render_sequences(state)
    moves_view = render_legal_moves(legal_moves)

    user_content = f"""Turn {state.turn_number} — You are player '{state.current_player}' ({state.chips[state.current_player]}).

{board_view}

{hand_view}

{seq_view}

Legal moves:
{moves_view}

Respond with JSON: {{\"move_index\": <int>}}"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_retry_messages(
    original_messages: list[dict],
    failed_response: str,
    error_reason: str,
    legal_moves: list,
) -> list[dict]:
    reminder = f"""Your previous response was invalid.

Your response: {failed_response}

Error: {error_reason}

Remember: respond with ONLY a JSON object: {{"move_index": <int>}}
Valid move indices: 0 through {len(legal_moves) - 1}

Try again."""

    return original_messages + [
        {"role": "assistant", "content": failed_response},
        {"role": "user", "content": reminder},
    ]