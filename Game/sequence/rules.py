from board import BOARD_LAYOUT, CARD_POSITIONS

TWO_EYED_JACKS = {'JH', 'JD'}
ONE_EYED_JACKS = {'JS', 'JC'}

def get_legal_moves(hand, board, player_chip, opponent_chip, locked_positions):
    legal_moves = []

    for card in hand:
        if card in TWO_EYED_JACKS:
            for pos, cell in BOARD_LAYOUT.items():
                if cell != 'XX' and board.get(pos) is None:
                    legal_moves.append({
                        'card': card,
                        'type': 'two_eyed_jack',
                        'position': pos
                    })

        elif card in ONE_EYED_JACKS:
            for pos, chip in board.items():
                if chip == opponent_chip and pos not in locked_positions:
                    legal_moves.append({
                        'card': card,
                        'type': 'one_eyed_jack',
                        'position': pos
                    })

        else:
            positions = CARD_POSITIONS.get(card, [])
            playable = [p for p in positions if board.get(p) is None]

            if not playable:
                legal_moves.append({
                    'card': card,
                    'type': 'dead_card',
                    'position': None
                })
            else:
                for pos in playable:
                    legal_moves.append({
                        'card': card,
                        'type': 'place',
                        'position': pos
                    })

    return legal_moves

def is_dead_card(card, board):
    """Check if a specific card is dead on the current board."""
    positions = CARD_POSITIONS.get(card, [])
    return all(board.get(p) is not None for p in positions)