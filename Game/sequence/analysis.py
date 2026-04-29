DIRECTIONS = [
    (0, 1),
    (1, 0),
    (1, 1),
    (1, -1),
]

CORNERS = {(0, 0), (0, 9), (9, 0), (9, 9)}


def _runs_in_direction(board, direction, player_chip):
    dr, dc = direction
    runs = []
    starts = set()

    if direction == (0, 1):
        starts = {(r, 0) for r in range(10)}
    elif direction == (1, 0):
        starts = {(0, c) for c in range(10)}
    elif direction == (1, 1):
        starts = {(0, c) for c in range(10)} | {(r, 0) for r in range(10)}
    elif direction == (1, -1):
        starts = {(0, c) for c in range(10)} | {(r, 9) for r in range(10)}

    seen = set()
    for sr, sc in starts:
        r, c = sr, sc
        run_chips = []
        run_positions = []

        while 0 <= r < 10 and 0 <= c < 10:
            key = (r, c, dr, dc)
            if key in seen:
                break
            seen.add(key)

            pos = (r, c)
            cell_chip = board.get(pos)
            is_corner = pos in CORNERS

            if cell_chip == player_chip or is_corner:
                run_chips.append(pos)
                run_positions.append(pos)
            else:
                if len(run_positions) >= 2:
                    runs.append(list(run_positions))
                run_chips = []
                run_positions = []

            r += dr
            c += dc

        if len(run_positions) >= 2:
            runs.append(list(run_positions))

    return runs


def find_partial_sequences(board, player_chip, min_length=3):
    result = []
    for direction in DIRECTIONS:
        for run in _runs_in_direction(board, direction, player_chip):
            if len(run) < min_length:
                continue

            dr, dc = direction
            own_positions = [p for p in run if board.get(p) == player_chip]

            positions_set = set(run)

            extending_before = _extending_pos(board, run[0], -dr, -dc, positions_set)
            extending_after = _extending_pos(board, run[-1], dr, dc, positions_set)
            extending = extending_before + extending_after

            result.append({
                "positions": run,
                "length": len(run),
                "own_count": len(own_positions),
                "corner_count": len(run) - len(own_positions),
                "extending_positions": extending,
                "direction": direction,
            })

    return result


def _extending_pos(board, anchor, dr, dc, exclude_set):
    positions = []
    r, c = anchor[0] + dr, anchor[1] + dc
    while 0 <= r < 10 and 0 <= c < 10:
        pos = (r, c)
        if pos in exclude_set:
            r += dr
            c += dc
            continue
        cell = board.get(pos)
        if cell is None:
            positions.append(pos)
            break
        elif pos in CORNERS:
            positions.append(pos)
            break
        else:
            break
    return positions


def _build_line_positions(board, start, direction):
    dr, dc = direction
    positions = []
    r, c = start
    while 0 <= r < 10 and 0 <= c < 10:
        positions.append((r, c))
        r += dr
        c += dc
    return positions


def find_completing_positions(board, player_chip):
    completing = {}
    for direction in DIRECTIONS:
        dr, dc = direction
        starts = _line_starts(direction)

        for sr, sc in starts:
            line = _build_line_positions(board, (sr, sc), direction)
            windows = _sliding_windows(line, 5)

            for window in windows:
                window_set = set(window)
                chip_count = sum(1 for p in window if board.get(p) == player_chip)
                corner_count = sum(1 for p in window if p in CORNERS and board.get(p) != player_chip)
                empty_in_window = [p for p in window if board.get(p) is None and p not in CORNERS]

                effective_count = chip_count + corner_count

                if effective_count == 4 and len(empty_in_window) == 1:
                    pos = empty_in_window[0]
                    completing.setdefault(pos, []).append({
                        "window": window,
                        "direction": direction,
                    })
                elif effective_count == 4 and len(empty_in_window) == 0:
                    for p in window:
                        if board.get(p) is None:
                            completing.setdefault(p, []).append({
                                "window": window,
                                "direction": direction,
                            })

    return completing


def find_threat_positions(board, opponent_chip):
    return find_completing_positions(board, opponent_chip)


def find_fork_positions(board, player_chip):
    completing = find_completing_positions(board, player_chip)
    fork_positions = {}
    for pos, completions in completing.items():
        if len(completions) >= 2:
            fork_positions[pos] = completions
    return fork_positions


def _line_starts(direction):
    dr, dc = direction
    starts = []
    if direction == (0, 1):
        starts = [(r, 0) for r in range(10)]
    elif direction == (1, 0):
        starts = [(0, c) for c in range(10)]
    elif direction == (1, 1):
        starts = [(0, c) for c in range(10)] + [(r, 0) for r in range(1, 10)]
    elif direction == (1, -1):
        starts = [(0, c) for c in range(10)] + [(r, 9) for r in range(1, 10)]
    return starts


def _sliding_windows(seq, size):
    if len(seq) < size:
        return []
    return [seq[i:i + size] for i in range(len(seq) - size + 1)]


def get_center_positions():
    result = set()
    center_rows = range(3, 7)
    center_cols = range(3, 7)
    for r in center_rows:
        for c in range(10):
            if (r, c) not in CORNERS:
                result.add((r, c))
    for c in center_cols:
        for r in range(10):
            if (r, c) not in CORNERS:
                result.add((r, c))
    return result


def get_key_center_positions():
    return {(3, 3), (3, 4), (3, 5), (3, 6),
            (4, 3), (4, 4), (4, 5), (4, 6),
            (5, 3), (5, 4), (5, 5), (5, 6),
            (6, 3), (6, 4), (6, 5), (6, 6)}


CATEGORIES = {
    "WINS": "wins",
    "BLOCKS_WIN": "blocks_win",
    "ADVANCES": "advances",
    "FORK": "fork",
    "CENTER": "center",
    "REMOVAL_OF_THREAT": "removal_of_threat",
    "REMOVAL": "removal",
    "WILD": "wild",
    "DEAD_CARD": "dead_card",
    "OTHER": "other",
}


def categorize_move(move, board, player_chip, opponent_chip, locked_positions):
    tags = set()

    if move["type"] == "dead_card":
        tags.add(CATEGORIES["DEAD_CARD"])
        return tags

    pos = move.get("position")
    if pos is None:
        tags.add(CATEGORIES["OTHER"])
        return tags

    completing_mine = find_completing_positions(board, player_chip)
    completing_opponent = find_completing_positions(board, opponent_chip)
    fork_mine = find_fork_positions(board, player_chip)

    if move["type"] == "one_eyed_jack":
        if pos in completing_opponent:
            tags.add(CATEGORIES["REMOVAL_OF_THREAT"])
        tags.add(CATEGORIES["REMOVAL"])
        return tags

    if pos in completing_mine:
        tags.add(CATEGORIES["WINS"])

    if pos in completing_opponent:
        tags.add(CATEGORIES["BLOCKS_WIN"])

    if pos in fork_mine:
        tags.add(CATEGORIES["FORK"])

    partials = find_partial_sequences(board, player_chip, min_length=2)
    for ps in partials:
        if pos in ps["extending_positions"] and CATEGORIES["WINS"] not in tags:
            tags.add(CATEGORIES["ADVANCES"])
            break

    center = get_key_center_positions()
    if pos in center and move["type"] == "two_eyed_jack":
        tags.add(CATEGORIES["CENTER"])

    if move["type"] == "two_eyed_jack":
        tags.add(CATEGORIES["WILD"])

    if not tags:
        tags.add(CATEGORIES["OTHER"])

    return tags


def get_strategic_two_eyed_jack_targets(board, player_chip, opponent_chip, max_targets=15):
    completing_mine = set(find_completing_positions(board, player_chip).keys())
    completing_opponent = set(find_completing_positions(board, opponent_chip).keys())
    fork_mine = set(find_fork_positions(board, player_chip).keys())
    center = get_key_center_positions()

    all_empty = {pos for pos, cell in board.items() if cell is None and pos not in CORNERS}

    priority = []
    seen = set()

    for pos in completing_mine & all_empty:
        if pos not in seen:
            priority.append((pos, "completes your sequence"))
            seen.add(pos)

    for pos in completing_opponent & all_empty:
        if pos not in seen:
            priority.append((pos, "blocks opponent sequence"))
            seen.add(pos)

    for pos in fork_mine & all_empty:
        if pos not in seen:
            priority.append((pos, "fork — threatens multiple completions"))
            seen.add(pos)

    partials = find_partial_sequences(board, player_chip, min_length=3)
    extending = set()
    for ps in partials:
        extending.update(ps["extending_positions"])
    for pos in extending & all_empty:
        if pos not in seen:
            priority.append((pos, "extends your near-sequence"))
            seen.add(pos)

    for pos in center & all_empty:
        if pos not in seen:
            priority.append((pos, "center control"))
            seen.add(pos)

    return priority[:max_targets]