# AI-Agents-Sequence-Game-Tournament

A benchmark for pitting LLM-backed agents against each other in the board game **Sequence**. Watch games live in the browser with the built-in visualizer, or run games from the CLI.

## Quickstart

```bash
pip install -e ".[dev]"
```

Requires Python >= 3.11.

## Running Games

### CLI — Single Game

```bash
# AI (Ollama/llama3) vs random CPU
python -m AI.run_game

# AI vs AI
python -m AI.run_game \
  --p1-provider openai  --p1-model gpt-4o \
  --p2-provider anthropic --p2-model claude-sonnet-4-20250514

# Extra options
python -m AI.run_game --verbose                        # debug logging
python -m AI.run_game --temperature 0.5                 # set LLM temperature
python -m AI.run_game --p1-temperature 0.7 --p2-temperature 0.2  # per-player temps
python -m AI.run_game --max-turns 300                   # cap game length
python -m AI.run_game --ollama-host http://host:11434   # custom Ollama host
```

### Visualizer — Start a Tournament and Watch Live

The visualizer is a FastAPI webapp that lets you start games between any combination of agents and stream the moves live to your browser.

```bash
# Start the visualizer server
python visualizer/backend.py
# → http://localhost:8000
```

Or with uvicorn directly:

```bash
uvicorn visualizer.backend:app --host 0.0.0.0 --port 8000
```

**Using the visualizer:**

1. Open http://localhost:8000 in your browser.
2. Click **New Game** — pick providers and models for each player (Ollama, OpenAI, or Anthropic).
3. Adjust the turn delay and click **Start Game**.
4. Watch the board update in real time as agents play.
5. Finished games are saved automatically — click **Past Games** to replay any previous match.

Game logs are persisted as JSON files in `visualizer/logs/`.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/games` | List all saved games |
| `GET` | `/api/games/{game_id}` | Load a specific game log |
| `POST` | `/api/games` | Start a new game (JSON body: `p1_provider`, `p1_model`, `p2_provider`, `p2_model`, `delay_ms`, `ollama_host`) |
| `WS` | `/ws/live` | WebSocket stream of live game events |

## Providers

| Provider | Requirements |
|----------|-------------|
| **Ollama** | Running Ollama server (`ollama serve`) |
| **OpenAI** | `OPENAI_API_KEY` env var |
| **Anthropic** | `ANTHROPIC_API_KEY` env var |

## Game Rules

- **Players**: 2 (each agent or random CPU)
- **Win condition**: First player to complete 2 sequences (5-in-a-row; diagonals count)
- **Deck**: 104 cards (2× each standard card). Jack of Hearts/Diamonds = wild (two-eyed), Jack of Spades/Clubs = removal (one-eyed)
- **Corners**: The four corner positions (XX) are wild for both players and cannot be removed

## Project Structure

```
Game/sequence/    Game engine (state, rules, board, deck, sequence detection)
AI/               LLM-backed agent, providers, prompt builder, parser, game runner
visualizer/       FastAPI backend + vanilla JS frontend for live game viewing
```

## Smoke Test

```bash
cd Game/sequence && python smoke_test.py   # 100 random vs random games
```