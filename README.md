# AI Agents — Sequence Game Tournament

A benchmarking framework that pits LLM-backed agents against each other in the board game **Sequence**. Born from a simple question — *what would happen if small language models played a board game against each other?* — this project grew from a single CPU opponent into a full round-robin tournament across six open-weight models.

> **Paper:** [Small Language Models as Strategic Agents in the Board Game Sequence](Paper/slm_sequence_tournament.pdf)

---

## Tournament Results

135 games across 3 full round-robin iterations, all run locally on a single NVIDIA RTX 4060 (8 GB).

| Rank | Model | Vendor | Params | Win % |
|------|-------|--------|--------|-------|
| 1 | Granite 4 Instruct | IBM | 3B | **80.0%** |
| 2 | Phi-4 Mini Instruct | Microsoft | 3.8B | 60.0% |
| 3 | Ministral 3 | Mistral | 3B | 53.3% |
| 3 | Gemma 4 | Google | 4B | 53.3% |
| 5 | Qwen 3.5 | Alibaba | 4B | 33.3% |
| 6 | Llama 3.2 | Meta | 3B | 20.0% |

Key findings: instruction-following quality outweighs parameter count at the 3–4B scale; a statistically significant first-mover advantage exists (58.5%, p ≈ 0.048); no model ever triggered the random-move fallback.

---

## Quickstart

```bash
pip install -e ".[dev]"
```

Requires Python ≥ 3.11 and a running [Ollama](https://ollama.com/) server for local models.

---

## Running the Tournament

Edit the `CONTESTANTS` array at the top of `tournament.sh`, then:

```bash
bash tournament.sh
```

Results are written to `tournament_logs/<timestamp>/`:
- `standings.csv` — final win/loss/draw counts per model
- `games.csv` — every game outcome (135 rows in the full run)
- `results/` — one `.result` file per game

### Analyzing Results

```bash
python visualizer/analyze.py tournament_logs/<timestamp>
```

Generates 15 PNG charts and a summary report in `visualizer/analysis_output/`. All charts used in the paper were produced by this script.

---

## Running a Single Game

```bash
# AI (Ollama) vs random CPU
python -m AI.run_game

# AI vs AI — mix providers freely
python -m AI.run_game \
  --p1-provider ollama  --p1-model granite4:3b \
  --p2-provider ollama  --p2-model llama3.2:3b

# Common options
python -m AI.run_game --temperature 0.3
python -m AI.run_game --max-turns 500
python -m AI.run_game --verbose
```

---

## Live Visualizer

A FastAPI + vanilla JS app that lets you watch games play out in real time in the browser.

```bash
python visualizer/backend.py
# → http://localhost:8000
```

Or with uvicorn:

```bash
uvicorn visualizer.backend:app --host 0.0.0.0 --port 8000
```

1. Open `http://localhost:8000`
2. Click **New Game** and pick providers/models for each player
3. Watch the board update move by move
4. Replay past games from the **Past Games** tab

Game logs are saved as JSON in `visualizer/logs/`.

### API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/games` | List all saved games |
| `GET` | `/api/games/{game_id}` | Load a specific game log |
| `POST` | `/api/games` | Start a new game |
| `WS` | `/ws/live` | WebSocket stream of live game events |

---

## Providers

| Provider | Setup |
|----------|-------|
| **Ollama** | `ollama serve` — models pulled on demand |
| **OpenAI** | `OPENAI_API_KEY` env var |
| **Anthropic** | `ANTHROPIC_API_KEY` env var |

---

## Game Rules (Brief)

- **Board:** 10 × 10 grid; four corner positions (XX) are permanently wild for both players
- **Win:** First to complete two non-overlapping sequences of five consecutive chips (horizontal, vertical, or diagonal)
- **Deck:** 104 cards (two standard decks). Two-eyed Jacks (JH, JD) place anywhere; one-eyed Jacks (JS, JC) remove an opponent chip
- **Hand:** 5 cards; draw one after each play

---

## Project Structure

```
Game/sequence/        Game engine — state, rules, board, deck, sequence detection
AI/                   LLM agent, providers (Ollama/OpenAI/Anthropic), prompt builder, parser
visualizer/           FastAPI backend, JS frontend, tournament analyzer
  analyze.py          Generates all 15 charts from tournament logs
  analysis_output/    Chart PNGs and summary report
tournament.sh         Round-robin tournament runner
tournament_logs/      Raw tournament output (CSV standings, game results)
Paper/                Research paper (LaTeX source + compiled PDF)
  slm_sequence_tournament.pdf
  slm_sequence_tournament.tex
  Images/             Figures used in the paper
```

---

## Reproducing the Paper

The full tournament is reproducible on consumer hardware (8 GB VRAM GPU recommended for running two concurrent games):

```bash
# 1. Pull all six models
ollama pull granite4:3b phi4-mini:3.8b ministral-3:3b gemma4:e4b qwen3.5:4b llama3.2:3b

# 2. Run the tournament (~6–9 hours for 3 full iterations)
bash tournament.sh

# 3. Analyze and generate charts
python visualizer/analyze.py tournament_logs/<timestamp>

# 4. Compile the paper
cd Paper && tectonic slm_sequence_tournament.tex
```

---

## Smoke Test

```bash
cd Game/sequence && python smoke_test.py   # 100 random-vs-random games
```
