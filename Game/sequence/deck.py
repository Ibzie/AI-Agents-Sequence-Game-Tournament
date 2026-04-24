import random

SUITS = ['S', 'H', 'D', 'C']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def build_deck():
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RNAKS] * 2
    random.shuffle(deck)
    return deck

def deal(deck, num_players=2, cards_per_player=7):
    hands = [[] for _ in range(num_players)]
    for i in range(cards_per_player):
        for players in range(num_players):
            hands[players].append(deck.pop())
    return hands, deck

def draw_card(hand, deck, discard_pile):
    if not deck:
        deck.extend(discard_pile)
        discard_pile.clear()
        random.shuffle(deck)
    hand.append(deck.pop())
    return hand, deck, discard_pile


