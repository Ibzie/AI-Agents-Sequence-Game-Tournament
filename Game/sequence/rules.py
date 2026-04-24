from board import BOARD_LAYOUT, CARD_POSITIONS

TWO_EYED_JACKS = {'JH', 'JD'}
ONE_EYED_JACKS = {'JS', 'JC'}

def get_legal_moves(hands, board, player_chip, opponent , locked_positions):
    legal_moves = []