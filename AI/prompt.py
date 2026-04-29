from Game.sequence.board import BOARD_LAYOUT
from Game.sequence.state import GameState
from Game.sequence.analysis import (
    find_partial_sequences,
    find_completing_positions,
    find_threat_positions,
    find_fork_positions,
    get_key_center_positions,
    categorize_move,
    get_strategic_two_eyed_jack_targets,
    CATEGORIES,
    CORNERS,
)

SYSTEM_PROMPT = """You are an expert Sequence board game player. Your goal is to complete 2 sequences (5 chips in a row, including diagonals) before your opponent. Corner positions (XX) are wild — they count toward any sequence for any player.

STRATEGY — decide in this priority order:
1. WIN: If you can complete your 2nd sequence, do it immediately.
2. BLOCK: If the opponent is one chip away from completing a sequence, block that position now — especially with a one-eyed jack removal.
3. FORK: Play where two of your near-sequences intersect. The opponent can only block one, so you complete the other next turn.
4. ADVANCE: Extend your longest near-sequence (3 or 4 in a row).
5. CENTER: Play near the board center (rows 3-6, cols 3-6). Center positions participate in up to 4 directions, giving you more sequence opportunities.
6. DISRUPT: If no offensive play is strong, consider removing an opponent chip that is part of their near-sequence.

CARD TYPES:
- Regular cards: Place your chip on one of the card's two board positions.
- Two-eyed jacks (JH, JD): Wild — place your chip on ANY empty non-corner space. These are rare (2 in 104 cards). Save for completing a sequence or creating a fork when possible.
- One-eyed jacks (JS, JC): Remove one opponent chip (not from a completed sequence, and not from a corner). These are rare (2 in 104 cards). Prioritize removing chips that are part of an opponent near-sequence.
- Dead card: Both positions for this card are occupied. Must discard it and draw a replacement.

NEAR-SEQUENCES indicate runs of 3+ consecutive chips (yours or corners) that could become a sequence. The board uses ! to mark positions that complete YOUR sequence and X to mark positions that complete the OPPONENT'S sequence.

The moves list is categorized with tags like [WIN], [BLOCK], [FORK], [ADVANCE], [CENTER], [REMOVAL]. Prioritize higher-category moves.

For two-eyed jacks, only strategic target positions are listed (completing, blocking, forking, extending, center). If you want to play a two-eyed jack on a position NOT listed, use: {"move_index": <index>, "position": [row, col]} where <index> is any two-eyed jack move index and [row, col] is the coordinate.

You MUST respond with ONLY a JSON object:
{"move_index": <integer>}
or for a wild jack on an unlisted position:
{"move_index": <index>, "position": [row, col]}"""


def render_board(state: GameState) -> str:
    completing_mine = set()
    completing_opp = set()
    opponent = [p for p in state.players if p != state.current_player][0]
    completing_mine = find_completing_positions(state.board, state.chips[state.current_player])
    completing_opp = find_completing_positions(state.board, state.chips[opponent])

    lines = []
    header = "     " + " ".join(f"{c:>5}" for c in range(10))
    lines.append(header)
    lines.append("    " + "-" * 55)
    for row in range(10):
        chip_strs = []
        for col in range(10):
            pos = (row, col)
            chip = state.board.get(pos)
            card = BOARD_LAYOUT[pos]
            marker = ""
            if pos in completing_mine:
                marker = "!"
            if pos in completing_opp:
                marker = "X" if not marker else "X"  # X takes priority for visibility
            if marker:
                # Show chip + marker
                if chip is not None:
                    chip_strs.append(f"{chip[0].upper()}@{card:>3}{marker}")
                elif card == "XX":
                    chip_strs.append(f"  XX {marker} ")
                else:
                    chip_strs.append(f" {card:>3}{marker} ")
            else:
                if chip is not None:
                    chip_strs.append(f"{chip[0].upper()}@{card:>3} ")
                elif card == "XX":
                    chip_strs.append("  XX   ")
                else:
                    chip_strs.append(f" {card:>3}  ")
        lines.append(f" {row:>2} |" + "|".join(chip_strs) + "|")
    lines.append("    " + "-" * 55)
    legend = "Chip colors:"
    for pid, chip_color in state.chips.items():
        legend += f" {pid}={chip_color[0].upper()}"
    legend += "  !=completes_yours  X=completes_opponent"
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


def render_near_sequences(state: GameState) -> str:
    current = state.current_player
    opponent = [p for p in state.players if p != current][0]
    current_chip = state.chips[current]
    opp_chip = state.chips[opponent]

    lines = []

    my_partials = find_partial_sequences(state.board, current_chip, min_length=3)
    if my_partials:
        lines.append("  Your near-sequences (3+ in a row):")
        for ps in sorted(my_partials, key=lambda x: x["length"], reverse=True)[:8]:
            positions_str = ", ".join(f"({p[0]},{p[1]})" for p in ps["positions"])
            ext_str = ", ".join(f"({p[0]},{p[1]})" for p in ps["extending_positions"])
            own = ps["own_count"]
            corners = ps["corner_count"]
            total = ps["length"]
            lines.append(f"    {total} in a row ({own} yours, {corners} corners): {positions_str} → completes at {ext_str}")
    else:
        lines.append("  No near-sequences yet.")

    opp_partials = find_partial_sequences(state.board, opp_chip, min_length=3)
    if opp_partials:
        lines.append("  Opponent near-sequences:")
        for ps in sorted(opp_partials, key=lambda x: x["length"], reverse=True)[:8]:
            positions_str = ", ".join(f"({p[0]},{p[1]})" for p in ps["positions"])
            ext_str = ", ".join(f"({p[0]},{p[1]})" for p in ps["extending_positions"])
            own = ps["own_count"]
            corners = ps["corner_count"]
            total = ps["length"]
            lines.append(f"    {total} in a row ({own} theirs, {corners} corners): {positions_str} → threatens {ext_str}")
    else:
        lines.append("  No opponent near-sequences detected.")

    return "\n".join(lines)


def render_move_history(state: GameState, n: int = 6) -> str:
    if not state.move_history:
        return "  (no previous moves)"

    recent = state.move_history[-n:]
    lines = []
    for pid, move in recent:
        if move["type"] == "dead_card":
            lines.append(f"    {pid}: discarded dead card {move['card']}")
        elif move["type"] == "place":
            pos = move["position"]
            lines.append(f"    {pid}: played {move['card']} at ({pos[0]},{pos[1]})")
        elif move["type"] == "two_eyed_jack":
            pos = move["position"]
            lines.append(f"    {pid}: played two-eyed jack {move['card']} (wild) at ({pos[0]},{pos[1]})")
        elif move["type"] == "one_eyed_jack":
            pos = move["position"]
            lines.append(f"    {pid}: played one-eyed jack {move['card']} — removed chip at ({pos[0]},{pos[1]})")
        else:
            lines.append(f"    {pid}: {move}")

    if len(state.move_history) > n:
        lines.append(f"    ... ({len(state.move_history) - n} earlier moves)")
    return "\n".join(lines)


def render_discard_summary(state: GameState) -> str:
    if not state.discard_pile:
        return "  (no cards discarded yet)"
    from collections import Counter
    counts = Counter(state.discard_pile)
    lines = []
    for card, count in sorted(counts.items()):
        lines.append(f"    {card}: {count}")
    return "\n".join(lines)


def render_legal_moves(state: GameState, legal_moves: list) -> str:
    opponent = [p for p in state.players if p != state.current_player][0]
    current_chip = state.chips[state.current_player]
    opp_chip = state.chips[opponent]

    # Categorize all moves
    categorized = []
    for i, move in enumerate(legal_moves):
        tags = categorize_move(move, state.board, current_chip, opp_chip, state.locked_positions)
        categorized.append((i, move, tags))

    # Group by priority category
    CATEGORY_ORDER = [
        CATEGORIES["WINS"],
        CATEGORIES["BLOCKS_WIN"],
        CATEGORIES["FORK"],
        CATEGORIES["ADVANCES"],
        CATEGORIES["REMOVAL_OF_THREAT"],
        CATEGORIES["CENTER"],
        CATEGORIES["REMOVAL"],
        CATEGORIES["WILD"],
        CATEGORIES["DEAD_CARD"],
        CATEGORIES["OTHER"],
    ]

    CATEGORY_LABELS = {
        CATEGORIES["WINS"]: "WIN",
        CATEGORIES["BLOCKS_WIN"]: "BLOCK",
        CATEGORIES["FORK"]: "FORK",
        CATEGORIES["ADVANCES"]: "ADVANCE",
        CATEGORIES["REMOVAL_OF_THREAT"]: "BLOCK-REMOVE",
        CATEGORIES["CENTER"]: "CENTER",
        CATEGORIES["REMOVAL"]: "REMOVAL",
        CATEGORIES["WILD"]: "WILD",
        CATEGORIES["DEAD_CARD"]: "DEAD",
        CATEGORIES["OTHER"]: "OTHER",
    }

    # Collect two-eyed jack moves separately
    wild_jack_moves = []
    regular_moves = []
    for i, move, tags in categorized:
        if move["type"] == "two_eyed_jack":
            wild_jack_moves.append((i, move, tags))
        else:
            regular_moves.append((i, move, tags))

    lines = []

    # Render non-wild moves grouped by category
    for cat in CATEGORY_ORDER:
        cat_label = CATEGORY_LABELS[cat]
        cat_moves = [(i, m, t) for i, m, t in regular_moves if cat in t]
        if not cat_moves:
            continue
        for i, move, tags in cat_moves:
            tag_strs = [CATEGORY_LABELS.get(t, t) for t in tags if t in CATEGORY_LABELS]
            tag_str = "+".join(tag_strs)
            desc = _describe_move(move)
            lines.append(f"  [{i}] [{tag_str}] {desc}")

    # Render two-eyed jack moves with strategic targets
    if wild_jack_moves:
        sample_index = wild_jack_moves[0][0]
        sample_move = wild_jack_moves[0][1]
        lines.append(f"  --- Two-eyed jack ({sample_move['card']}) — wild, playable on any empty non-corner position ---")

        targets = get_strategic_two_eyed_jack_targets(
            state.board, current_chip, opp_chip, max_targets=15
        )

        if targets:
            lines.append("  Strategic placement targets:")
            for pos, reason in targets:
                tag_str = "WILD"
                # Check if this position also has other tags
                test_move = {"type": "two_eyed_jack", "card": sample_move["card"], "position": pos}
                extra_tags = categorize_move(test_move, state.board, current_chip, opp_chip, state.locked_positions)
                extra_labels = [CATEGORY_LABELS.get(t, t) for t in extra_tags if t != CATEGORIES["WILD"] and t in CATEGORY_LABELS]
                if extra_labels:
                    tag_str += "+" + "+".join(extra_labels)
                lines.append(f"    [{sample_index}] place at ({pos[0]},{pos[1]}) [{tag_str}] {reason}")
        else:
            lines.append("  No high-value strategic targets found — any center-area empty position is reasonable.")

        wild_cards_in_hand = len(set(m["card"] for _, m, _ in wild_jack_moves))
        if wild_cards_in_hand > 1:
            lines.append(f"  (You have {wild_cards_in_hand} two-eyed jack cards in hand)")

    return "\n".join(lines)


def _describe_move(move: dict) -> str:
    if move["type"] == "dead_card":
        return f"Discard dead card {move['card']} and draw replacement"
    elif move["type"] == "place":
        pos = move["position"]
        return f"Play {move['card']} at ({pos[0]},{pos[1]})"
    elif move["type"] == "one_eyed_jack":
        pos = move["position"]
        return f"Remove opponent chip at ({pos[0]},{pos[1]}) with {move['card']}"
    elif move["type"] == "two_eyed_jack":
        pos = move["position"]
        return f"Play wild {move['card']} at ({pos[0]},{pos[1]})"
    return f"{move['type']} {move.get('card', '')}"


def build_messages(state: GameState, legal_moves: list) -> list[dict]:
    board_view = render_board(state)
    hand_view = render_hand(state)
    seq_view = render_sequences(state)
    near_view = render_near_sequences(state)
    moves_view = render_legal_moves(state, legal_moves)
    history_view = render_move_history(state)
    discard_view = render_discard_summary(state)

    user_content = f"""Turn {state.turn_number} — You are player '{state.current_player}' ({state.chips[state.current_player]}).

{board_view}

{hand_view}

{seq_view}

Near-sequences:
{near_view}

Recent moves:
{history_view}

Discarded cards (no longer available):
{discard_view}

Legal moves:
{moves_view}

Respond with JSON: {{"move_index": <int>}} or for a wild jack on an unlisted position: {{"move_index": <wild_jack_index>, "position": [row, col]}}"""

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
For a wild jack on an unlisted position: {{"move_index": <wild_jack_index>, "position": [row, col]}}
Valid move indices: 0 through {len(legal_moves) - 1}

Try again."""

    return original_messages + [
        {"role": "assistant", "content": failed_response},
        {"role": "user", "content": reminder},
    ]