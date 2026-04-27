DIRECTIONS = [
    (0, 1),   # horizontal
    (1, 0),   # vertical
    (1, 1),   # diagonal down-right
    (1, -1),  # diagonal down-left
]

def get_sequences(board, player_chip):
    """Find all completed sequences for a given player chip.
    Returns a list of sequences, each sequence is a frozenset of (row,col) positions.
    Corners (XX) count as wild — they belong to everyone.
    """
    found = []

    for direction in DIRECTIONS:
        dr, dc = direction
        checked = set()

        for row in range(10):
            for col in range(10):
                if (row, col) in checked:
                    continue

                run = []
                r, c = row, col

                while 0 <= r < 10 and 0 <= c < 10:
                    cell_chip = board.get((r, c))
                    is_corner = (r, c) in {(0,0), (0,9), (9,0), (9,9)}

                    if cell_chip == player_chip or is_corner:
                        run.append((r, c))
                    else:
                        if len(run) >= 5:
                            found.append(frozenset(run[-5:]))
                        run = []

                    checked.add((r, c))
                    r += dr
                    c += dc

                if len(run) >= 5:
                    found.append(frozenset(run[-5:]))

    # Deduplicate
    return list({s for s in found})

def get_locked_positions(board, chips):
    """Return all positions that are part of any completed sequence
    for any player — these cannot be removed by one-eyed jacks.
    """
    locked = set()
    for chip in chips:
        for seq in get_sequences(board, chip):
            locked.update(seq)
    return locked

def count_sequences(board, player_chip):
    return len(get_sequences(board, player_chip))