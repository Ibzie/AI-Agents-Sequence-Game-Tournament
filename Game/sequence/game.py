import copy
from .rules import get_legal_moves
from .player_actions import play_card, play_two_eyed_jack, play_one_eyed_jack, discard_dead_card
from .sequence_detector import count_sequences, get_locked_positions
from .deck import draw_card

SEQUENCES_TO_WIN = 2


def get_moves_for_current_player(state):
    opponent = [p for p in state.players if p != state.current_player][0]
    return get_legal_moves(
        hand=state.hands[state.current_player],
        board=state.board,
        player_chip=state.chips[state.current_player],
        opponent_chip=state.chips[opponent],
        locked_positions=state.locked_positions,
    )


def apply_move(state, move):
    state = copy.deepcopy(state)
    player = state.current_player
    opponent = [p for p in state.players if p != player][0]
    player_chip = state.chips[player]
    move_type = move['type']
    card = move['card']
    position = move['position']

    if move_type == 'dead_card':
        state.hands[player], state.deck, state.discard_pile = discard_dead_card(
            state.hands[player], state.deck, state.discard_pile, card
        )
    elif move_type == 'place':
        state.hands[player], state.discard_pile, state.board = play_card(
            state.hands[player], state.discard_pile, card, state.board, position, player_chip
        )
        state.hands[player], state.deck, state.discard_pile = draw_card(
            state.hands[player], state.deck, state.discard_pile
        )
    elif move_type == 'two_eyed_jack':
        state.hands[player], state.discard_pile, state.board = play_two_eyed_jack(
            state.hands[player], state.discard_pile, card, state.board, position, player_chip
        )
        state.hands[player], state.deck, state.discard_pile = draw_card(
            state.hands[player], state.deck, state.discard_pile
        )
    elif move_type == 'one_eyed_jack':
        state.hands[player], state.discard_pile, state.board = play_one_eyed_jack(
            state.hands[player], state.discard_pile, card, state.board, position
        )

    state.sequences[player] = count_sequences(state.board, player_chip)
    state.sequences[opponent] = count_sequences(state.board, state.chips[opponent])
    state.locked_positions = get_locked_positions(state.board, state.chips.values())

    if state.sequences[player] >= SEQUENCES_TO_WIN:
        state.winner = player
    elif state.sequences[opponent] >= SEQUENCES_TO_WIN:
        state.winner = opponent

    if not state.winner:
        idx = state.players.index(player)
        state.current_player = state.players[(idx + 1) % len(state.players)]

    state.move_history.append((player, move))
    state.turn_number += 1
    return state


def is_game_over(state):
    return state.winner is not None