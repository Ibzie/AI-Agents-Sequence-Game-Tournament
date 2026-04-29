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


def run_game_vs_cpu(ai_agent: LLMAgent, cpu_player: str = "cpu", max_turns: int = 500):
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
            logger.info(f"--- Turn {state.turn_number}: {current} (AI/{ai_agent.model}) ---")
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


def run_game_vs_llm(agent1: LLMAgent, agent2: LLMAgent, max_turns: int = 500):
    players = [agent1.player_id, agent2.player_id]
    chips = {agent1.player_id: "blue", agent2.player_id: "green"}

    state = init_game(player_ids=players, chips=chips)
    logger.info(f"Game started: {agent1.player_id} ({agent1.model}) vs {agent2.player_id} ({agent2.model})")

    agent_map = {agent1.player_id: agent1, agent2.player_id: agent2}

    while not is_game_over(state) and state.turn_number < max_turns:
        current = state.current_player
        moves = get_moves_for_current_player(state)

        if not moves:
            logger.warning(f"No legal moves for {current}. Game ends in draw.")
            break

        agent = agent_map[current]
        logger.info(f"--- Turn {state.turn_number}: {current} ({agent.model}) ---")
        move = agent.choose_move(state, moves)

        logger.info(
            f"  {current} plays: type={move['type']} card={move['card']} "
            f"pos={move.get('position')}"
        )

        state = apply_move(state, move)

        for pid in state.players:
            logger.info(f"  {pid} sequences: {state.sequences[pid]}")

    print("\n" + "=" * 60)
    if state.winner:
        winner_agent = agent_map[state.winner]
        print(f"  WINNER: {state.winner} ({winner_agent.model}) in {state.turn_number} turns")
    else:
        print(f"  DRAW after {state.turn_number} turns")
    print("=" * 60)

    for pid in state.players:
        agent = agent_map[pid]
        print(f"  {pid} ({agent.model}): {state.sequences[pid]} sequences")
    print()

    return state


def main():
    parser = argparse.ArgumentParser(description="AI vs CPU or AI vs AI Sequence Game")
    parser.add_argument(
        "--provider", default="ollama",
        choices=["ollama", "openai", "anthropic"],
        help="LLM provider (default: ollama)",
    )
    parser.add_argument("--model", default=None, help="Model name (provider-specific default if omitted)")
    parser.add_argument("--temperature", type=float, default=0.3, help="LLM temperature (default: 0.3)")
    parser.add_argument("--player-id", default="ai", help="AI player ID (default: ai)")
    parser.add_argument("--cpu-id", default="cpu", help="CPU player ID (default: cpu)")
    parser.add_argument("--max-turns", type=int, default=500, help="Max turns before draw (default: 500)")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama host URL")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    # AI vs AI args
    parser.add_argument("--p1-provider", default=None, choices=["ollama", "openai", "anthropic"], help="Player 1 LLM provider (enables AI vs AI mode)")
    parser.add_argument("--p1-model", default=None, help="Player 1 model name")
    parser.add_argument("--p2-provider", default=None, choices=["ollama", "openai", "anthropic"], help="Player 2 LLM provider")
    parser.add_argument("--p2-model", default=None, help="Player 2 model name")
    parser.add_argument("--p1-id", default="player1", help="Player 1 ID in AI vs AI mode (default: player1)")
    parser.add_argument("--p2-id", default="player2", help="Player 2 ID in AI vs AI mode (default: player2)")
    parser.add_argument("--p1-temperature", type=float, default=None, help="Player 1 temperature")
    parser.add_argument("--p2-temperature", type=float, default=None, help="Player 2 temperature")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    model_defaults = {"ollama": "llama3", "openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}

    ollama_host = args.ollama_host

    # AI vs AI mode
    if args.p1_model or args.p2_model or args.p1_provider or args.p2_provider:
        p1_provider_name = args.p1_provider or args.provider
        p2_provider_name = args.p2_provider or args.provider
        p1_model = args.p1_model or model_defaults.get(p1_provider_name, "llama3")
        p2_model = args.p2_model or model_defaults.get(p2_provider_name, "llama3")
        p1_temp = args.p1_temperature if args.p1_temperature is not None else args.temperature
        p2_temp = args.p2_temperature if args.p2_temperature is not None else args.temperature

        p1_kwargs = {}
        if p1_provider_name == "ollama":
            p1_kwargs["host"] = ollama_host
        p2_kwargs = {}
        if p2_provider_name == "ollama":
            p2_kwargs["host"] = ollama_host

        p1_provider = get_provider(p1_provider_name, **p1_kwargs)
        p2_provider = get_provider(p2_provider_name, **p2_kwargs)

        agent1 = LLMAgent(
            provider=p1_provider, model=p1_model,
            temperature=p1_temp, player_id=args.p1_id,
        )
        agent2 = LLMAgent(
            provider=p2_provider, model=p2_model,
            temperature=p2_temp, player_id=args.p2_id,
        )

        logger.info(f"Player 1: provider={p1_provider_name}, model={p1_model}, temp={p1_temp}")
        logger.info(f"Player 2: provider={p2_provider_name}, model={p2_model}, temp={p2_temp}")

        return run_game_vs_llm(agent1, agent2, max_turns=args.max_turns)

    # Original AI vs CPU mode
    provider_kwargs = {}
    if args.provider == "ollama":
        provider_kwargs["host"] = ollama_host

    provider = get_provider(args.provider, **provider_kwargs)
    model = args.model or model_defaults.get(args.provider, "llama3")

    ai_agent = LLMAgent(
        provider=provider,
        model=model,
        temperature=args.temperature,
        player_id=args.player_id,
    )

    logger.info(f"AI Agent: provider={args.provider}, model={model}, player={args.player_id}")
    logger.info(f"CPU opponent: {args.cpu_id} (random)")

    state = run_game_vs_cpu(ai_agent, cpu_player=args.cpu_id, max_turns=args.max_turns)
    return state


if __name__ == "__main__":
    main()