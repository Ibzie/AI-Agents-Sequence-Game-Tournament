import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Game.sequence.state import init_game
from Game.sequence.game import apply_move, get_moves_for_current_player, is_game_over
from Game.sequence.random_agent import random_agent

from AI.llm_agent import LLMAgent
from AI.providers import get_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_game")


def run_game(ai_agent: LLMAgent, cpu_player: str = "cpu", max_turns: int = 500):
    players = [ai_agent.player_id, cpu_player]
    chips = {ai_agent.player_id: "blue", cpu_player: "green"}

    state = init_game(player_ids=players, chips=chips)
    logger.info(f"Game started: {players} with chips {chips}")

    while not is_game_over(state) and state.turn_number < max_turns:
        current = state.current_player
        moves = get_moves_for_current_player(state)

        if not moves:
            logger.warning(f"No legal moves for {current}. Game ends in draw.")
            break

        if current == ai_agent.player_id:
            logger.info(f"--- Turn {state.turn_number}: {current} (AI) ---")
            move = ai_agent.choose_move(state, moves)
        else:
            logger.info(f"--- Turn {state.turn_number}: {current} (CPU/random) ---")
            move = random_agent(moves)

        logger.info(
            f"  {current} plays: type={move['type']} card={move['card']} "
            f"pos={move.get('position')}"
        )

        state = apply_move(state, move)

        for pid in state.players:
            logger.info(f"  {pid} sequences: {state.sequences[pid]}")

    print("\n" + "=" * 60)
    if state.winner:
        winner_label = "AI" if state.winner == ai_agent.player_id else "CPU"
        print(f"  WINNER: {state.winner} ({winner_label}) in {state.turn_number} turns")
    else:
        print(f"  DRAW after {state.turn_number} turns")
    print("=" * 60)

    for pid in state.players:
        print(f"  {pid} sequences: {state.sequences[pid]}")
    print()

    return state


def main():
    parser = argparse.ArgumentParser(description="AI vs CPU Sequence Game")
    parser.add_argument(
        "--provider", default="ollama",
        choices=["ollama", "openai", "anthropic"],
        help="LLM provider (default: ollama)",
    )
    parser.add_argument("--model", default=None, help="Model name (provider-specific default if omitted)")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature (default: 0.7)")
    parser.add_argument("--player-id", default="ai", help="AI player ID (default: ai)")
    parser.add_argument("--cpu-id", default="cpu", help="CPU player ID (default: cpu)")
    parser.add_argument("--max-turns", type=int, default=500, help="Max turns before draw (default: 500)")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama host URL")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    model_defaults = {"ollama": "llama3", "openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}
    model = args.model or model_defaults.get(args.provider, "llama3")

    provider_kwargs = {}
    if args.provider == "ollama":
        provider_kwargs["host"] = args.ollama_host

    provider = get_provider(args.provider, **provider_kwargs)

    ai_agent = LLMAgent(
        provider=provider,
        model=model,
        temperature=args.temperature,
        player_id=args.player_id,
    )

    logger.info(f"AI Agent: provider={args.provider}, model={model}, player={args.player_id}")
    logger.info(f"CPU opponent: {args.cpu_id} (random)")

    state = run_game(ai_agent, cpu_player=args.cpu_id, max_turns=args.max_turns)
    return state


if __name__ == "__main__":
    main()