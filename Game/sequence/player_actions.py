from .deck import draw_card

def play_card(hand, discard_pile, card, board, position, player_chip):
    hand.remove(card)
    discard_pile.append(card)
    board[position] = player_chip
    return hand, discard_pile, board

def play_two_eyed_jack (hand, discard_pile, card, board, position, player_chip):
    hand.remove(card)
    discard_pile.append(card)
    board[position] = player_chip
    return hand, discard_pile, board

def play_one_eyed_jack (hand, discard_pile, card, board, position):
    hand.remove(card)
    discard_pile.append(card)
    board[position] = None
    return hand, discard_pile, board

def discard_dead_card(hand, deck, discard_pile, card):
    hand.remove(card)
    discard_pile.append(card)
    hand, deck, discard_pile = draw_card(hand, deck, discard_pile)
    return hand, deck, discard_pile 