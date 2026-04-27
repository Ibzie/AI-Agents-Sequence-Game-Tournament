from state import init_game
from game import apply_move, get_moves_for_current_player, is_game_over
from random_agent import random_agent

def run_game():
    state = init_game(
        player_ids=['p1', 'p2'],
        chips={'p1': 'blue', 'p2': 'green'}
    )

    max_turns = 500
    while not is_game_over(state) and state.turn_number < max_turns:
        moves = get_moves_for_current_player(state)
        if not moves:
            break
        move = random_agent(moves)
        state = apply_move(state, move)

    return state

if __name__ == "__main__":
    print("Running 100 random games...\n")

    results = {'p1': 0, 'p2': 0, 'draw': 0}
    turn_counts = []
    errors = 0

    for i in range(100):
        try:
            state = run_game()
            if state.winner:
                results[state.winner] += 1
            else:
                results['draw'] += 1
            turn_counts.append(state.turn_number)
        except Exception as e:
            errors += 1
            print(f"Game {i+1} ERROR: {e}")

    print(f"Results over 100 games:")
    print(f"  p1 wins:  {results['p1']}")
    print(f"  p2 wins:  {results['p2']}")
    print(f"  draws:    {results['draw']}")
    print(f"  errors:   {errors}")
    print(f"  avg turns: {sum(turn_counts) / len(turn_counts):.1f}" if turn_counts else "  no completed games")