# AGENTS.md

## Project

Two-package Python project: AI agents play the board game "Sequence" against each other or a random CPU opponent.
- `Game/sequence/` — game engine (state, rules, board, deck, sequence detection, strategic analysis)
- `AI/` — LLM-backed agent with pluggable providers (Ollama, OpenAI, Anthropic)

Requires Python >=3.11.

## Commands

```bash
pip install -e ".[dev]"

# AI vs CPU (default: Ollama/llama3)
python -m AI.run_game
python -m AI.run_game --provider openai --model gpt-4o
python -m AI.run_game --provider anthropic --model claude-sonnet-4-20250514
python -m AI.run_game --verbose

# AI vs AI mode (uses --p1-provider / --p2-provider flags)
python -m AI.run_game --p1-provider openai --p1-model gpt-4o --p2-provider anthropic --p2-model claude-sonnet-4-20250514

# Smoke test the game engine (random vs random, 100 games)
python Game/sequence/smoke_test.py   # must run from inside Game/sequence/
```

# Visualizer (live game viewer webapp)
python visualizer/backend.py                      # starts on http://localhost:8000
# Or with uvicorn directly:
uvicorn visualizer.backend:app --host 0.0.0.0 --port 8000

# Game logs are stored in visualizer/logs/ as JSON files
```

No test suite, linter, formatter, typechecker, or CI exists yet.

## Architecture

- **State is immutable**: `apply_move` (`game.py`) deep-copies `GameState` before mutating. Never mutate state in-place.
- **Legal moves are plain dicts** with keys `type` (`place`, `two_eyed_jack`, `one_eyed_jack`, `dead_card`), `card`, and `position` (tuple or None).
- **LLM response format**: `{"move_index": <int>}` for normal moves, `{"move_index": <int>, "position": [row, col]}` for wild jack placements on unlisted positions. Parser (`AI/parser.py`) uses cascading fallback: strict JSON → regex JSON extraction → regex position extraction → bare number extraction.
- **LLM agent** (`AI/llm_agent.py`) retries up to 3 times on parse failure, then falls back to random move. Default temperature 0.3.
- **Prompt builder** (`AI/prompt.py`) filters two-eyed jack moves to ~15 strategic targets instead of listing all ~80 empty positions. The game engine still generates all positions for validation.
- **Strategic analysis** (`analysis.py`) uses sliding-window for completing positions and a separate run-based method for partial sequences. Both treat corner positions (XX) as wild.
- **Provider abstraction** (`AI/providers/base.py`): add new providers by subclassing `BaseProvider` and registering in `AI/providers/__init__.py`.
- **Visualizer** (`visualizer/`): FastAPI backend + vanilla JS frontend. `backend.py` serves the SPA, provides REST + WebSocket APIs, and runs games in-thread. Game events stream to connected browsers via WebSocket. `AI/game_log.py` handles persistence (JSON files in `visualizer/logs/`). `AI/game_runner.py` is the event-emitting game loop that replaces the tight CLI loop for the visualizer.

## Game Rules

- 2-player only. Win condition: 2 sequences (5-in-a-row; diagonals count).
- Deck: 2 copies of each standard card (104 total). JH/JD = two-eyed wild; JS/JC = one-eyed removal jack.
- Corner positions (XX) are wild for both players and cannot be removed.

## Gotchas

- `smoke_test.py` uses bare relative imports (`from state import ...`) — only works when run from inside `Game/sequence/`.
- `AI/run_game.py` inserts parent dir into `sys.path` for cross-package imports. Always run as `python -m AI.run_game` from repo root.
- Ollama provider detects "thinking" models (prefixes: `qwen3`, `qwq`, `deepseek-r1`) and sets `think: False` in the API payload; also falls back to extracting JSON from the `thinking` field if `content` is empty.
- OpenAI/Anthropic providers require `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env vars. Ollama requires a running Ollama server.
- One-eyed jack moves in `rules.py` use the key `one_eyed_jack` (with underscore `s`), but `move_type` comparison in `game.py:apply_move` also uses `one_eyed_jack`.