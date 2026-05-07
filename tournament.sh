#!/usr/bin/env bash
# tournament.sh — Round-robin AI Sequence Game Tournament
#
# Usage:
#   bash tournament.sh          Run the tournament with settings below
#   bash tournament.sh --help   Show this help
#
# Edit the CONFIGURATION section to set contestants and parameters.
# Required env vars: ANTHROPIC_API_KEY (for anthropic), OPENAI_API_KEY (for openai)

set -euo pipefail

# ===========================================================================
# CONFIGURATION — edit this section
# ===========================================================================

# Number of full round-robin iterations to run.
# Each iteration: every contestant plays every other contestant once.
TOURNAMENT_ITERATIONS=3

# Games per head-to-head matchup (Best-of-3).
GAMES_PER_MATCH=3

# Maximum games running in parallel.
MAX_CONCURRENT=2

# Maximum turns before a game is declared a draw.
MAX_TURNS=500

# LLM temperature applied to all players (0.0 = deterministic, 1.0 = creative).
TEMPERATURE=0.3

# Ollama server URL — only relevant when a contestant uses the "ollama" provider.
OLLAMA_HOST="http://localhost:11434"

# Python interpreter command. Leave blank to auto-detect.
# Examples: "python", "python3", "uv run python"
PYTHON_CMD=""

# Contestants — format: "provider:model"
# Supported providers: ollama | openai | anthropic
CONTESTANTS=(
    "ollama:granite4:3b"
    "ollama:ministral-3:3b"
    "ollama:qwen3.5:4b"
    "ollama:gemma4:e4b"
    "ollama:phi4-mini:3.8b"
    "ollama:llama3.2:3b"
)

# Root output directory; a timestamped subfolder is created per run.
LOG_BASE_DIR="tournament_logs"

# ===========================================================================
# END CONFIGURATION
# ===========================================================================

# ── internals ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_BASE_DIR}/${RUN_TS}"
RESULTS_DIR="${LOG_DIR}/results"
GAMES_DIR="${LOG_DIR}/games"
ACTIVE_PIDS=()

# ── helpers ─────────────────────────────────────────────────────────────────
log() { printf '  %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
hr()  { printf '%.0s─' {1..70}; printf '\n'; }

usage() {
    grep '^#' "$0" | head -10 | sed 's/^# \{0,1\}//'
    exit 0
}

resolve_python() {
    [[ -n "$PYTHON_CMD" ]] && return
    if command -v uv &>/dev/null; then
        PYTHON_CMD="uv run python"
    elif command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        die "No Python found. Set PYTHON_CMD in the configuration section."
    fi
}

# Remove finished PIDs from ACTIVE_PIDS.
reap_jobs() {
    local live=()
    for pid in "${ACTIVE_PIDS[@]+"${ACTIVE_PIDS[@]}"}"; do
        kill -0 "$pid" 2>/dev/null && live+=("$pid")
    done
    ACTIVE_PIDS=("${live[@]+"${live[@]}"}")
}

# Block until fewer than MAX_CONCURRENT jobs are running.
throttle() {
    while true; do
        reap_jobs
        [[ ${#ACTIVE_PIDS[@]} -lt $MAX_CONCURRENT ]] && return
        sleep 0.5
    done
}

# Block until all active background jobs finish.
wait_all() {
    for pid in "${ACTIVE_PIDS[@]+"${ACTIVE_PIDS[@]}"}"; do
        wait "$pid" 2>/dev/null || true
    done
    ACTIVE_PIDS=()
}

# ── game runner ──────────────────────────────────────────────────────────────
# Launch one game in the background, write a .result file when it finishes.
# Args: <p1_key> <p2_key> <game_id>   where key = "provider:model"
run_game_bg() {
    local p1_key="$1" p2_key="$2" game_id="$3"
    local p1_provider="${p1_key%%:*}" p1_model="${p1_key#*:}"
    local p2_provider="${p2_key%%:*}" p2_model="${p2_key#*:}"
    local log_file="${GAMES_DIR}/${game_id}.log"
    local result_file="${RESULTS_DIR}/${game_id}.result"

    (
        cd "$SCRIPT_DIR"
        # Word-split PYTHON_CMD intentionally (e.g. "uv run python" → 3 tokens).
        # shellcheck disable=SC2086
        if $PYTHON_CMD -m AI.run_game \
                --p1-provider "$p1_provider" --p1-model "$p1_model" --p1-id "p1" \
                --p2-provider "$p2_provider" --p2-model "$p2_model" --p2-id "p2" \
                --max-turns   "$MAX_TURNS" \
                --temperature "$TEMPERATURE" \
                --ollama-host "$OLLAMA_HOST" \
                >"$log_file" 2>&1
        then
            # run_game.py prints "  WINNER: p1 (model) in N turns" or "  DRAW after N turns"
            if   grep -qE "^\s+WINNER: p1 " "$log_file"; then
                printf '%s %s p1_wins\n' "$p1_key" "$p2_key"
            elif grep -qE "^\s+WINNER: p2 " "$log_file"; then
                printf '%s %s p2_wins\n' "$p1_key" "$p2_key"
            else
                printf '%s %s draw\n'    "$p1_key" "$p2_key"
            fi
        else
            log "FAILED game $game_id (see ${log_file})" >&2
            printf '%s %s error\n' "$p1_key" "$p2_key"
        fi >"$result_file"
    ) &

    ACTIVE_PIDS+=("$!")
}

# ── results aggregation ──────────────────────────────────────────────────────
# Populates globals: wins[] losses[] draws[] (keyed by contestant string).
aggregate_results() {
    declare -gA wins losses draws
    local c
    for c in "${CONTESTANTS[@]}"; do
        wins[$c]=0; losses[$c]=0; draws[$c]=0
    done
    local f p1 p2 outcome
    for f in "${RESULTS_DIR}"/*.result; do
        [[ -f "$f" ]] || continue
        read -r p1 p2 outcome <"$f"
        case "$outcome" in
            p1_wins) wins[$p1]=$(( wins[$p1]+1 )); losses[$p2]=$(( losses[$p2]+1 )) ;;
            p2_wins) wins[$p2]=$(( wins[$p2]+1 )); losses[$p1]=$(( losses[$p1]+1 )) ;;
            draw)    draws[$p1]=$(( draws[$p1]+1 )); draws[$p2]=$(( draws[$p2]+1 )) ;;
        esac
    done
}

print_standings() {
    aggregate_results

    echo ""
    hr
    printf '  %-42s  %5s %5s %5s  %7s  %6s\n' "Model" "W" "L" "D" "Games" "Win%"
    hr

    local c rows=()
    for c in "${CONTESTANTS[@]}"; do
        local w="${wins[$c]}" l="${losses[$c]}" d="${draws[$c]}"
        local total=$(( w + l + d ))
        # Win% = (W + 0.5×D) / total × 100; stored ×100 for integer sort
        local sort_score=$(( w * 100 + d * 50 ))
        local win_pct=0
        [[ $total -gt 0 ]] && win_pct=$(( (w * 200 + d * 100) / (total * 2) ))
        rows+=("$sort_score $w $l $d $total $win_pct $c")
    done

    printf '%s\n' "${rows[@]}" | sort -rn | \
    while read -r _score w l d total win_pct model; do
        printf '  %-42s  %5d %5d %5d  %7d  %5d%%\n' \
            "$model" "$w" "$l" "$d" "$total" "$win_pct"
    done
    hr
}

print_head2head() {
    local nc="${#CONTESTANTS[@]}"
    (( nc >= 2 )) || return 0

    declare -A hw hl hd  # head-to-head wins/losses/draws keyed "p1|p2"
    local f p1 p2 outcome
    for f in "${RESULTS_DIR}"/*.result; do
        [[ -f "$f" ]] || continue
        read -r p1 p2 outcome <"$f"
        case "$outcome" in
            p1_wins)
                hw["${p1}|${p2}"]=$(( ${hw["${p1}|${p2}"]:-0}+1 ))
                hl["${p2}|${p1}"]=$(( ${hl["${p2}|${p1}"]:-0}+1 ))
                ;;
            p2_wins)
                hw["${p2}|${p1}"]=$(( ${hw["${p2}|${p1}"]:-0}+1 ))
                hl["${p1}|${p2}"]=$(( ${hl["${p1}|${p2}"]:-0}+1 ))
                ;;
            draw)
                hd["${p1}|${p2}"]=$(( ${hd["${p1}|${p2}"]:-0}+1 ))
                hd["${p2}|${p1}"]=$(( ${hd["${p2}|${p1}"]:-0}+1 ))
                ;;
        esac
    done

    echo ""
    echo "  HEAD-TO-HEAD  (row vs column — W-L-D from row's perspective)"
    echo ""

    local abbrevs=() c
    for c in "${CONTESTANTS[@]}"; do abbrevs+=("${c#*:}"); done

    # Header
    printf '  %-28s' ""
    local ab
    for ab in "${abbrevs[@]}"; do printf ' %-16s' "${ab:0:16}"; done
    echo ""

    local i j
    for (( i=0; i<nc; i++ )); do
        printf '  %-28s' "${abbrevs[$i]:0:28}"
        for (( j=0; j<nc; j++ )); do
            if (( i == j )); then
                printf ' %-16s' "---"
            else
                local key="${CONTESTANTS[$i]}|${CONTESTANTS[$j]}"
                local w="${hw[$key]:-0}" l="${hl[$key]:-0}" d="${hd[$key]:-0}"
                printf ' %-16s' "${w}-${l}-${d}"
            fi
        done
        echo ""
    done
    echo ""
}

save_csv() {
    local standings_csv="${LOG_DIR}/standings.csv"
    {
        echo "model,wins,losses,draws,total,win_pct"
        local c
        for c in "${CONTESTANTS[@]}"; do
            local w="${wins[$c]}" l="${losses[$c]}" d="${draws[$c]}"
            local total=$(( w + l + d ))
            local win_pct=0
            [[ $total -gt 0 ]] && win_pct=$(( (w * 200 + d * 100) / (total * 2) ))
            printf '%s,%d,%d,%d,%d,%d\n' "$c" "$w" "$l" "$d" "$total" "$win_pct"
        done
    } >"$standings_csv"

    local games_csv="${LOG_DIR}/games.csv"
    {
        echo "game_id,p1_model,p2_model,outcome"
        local f
        for f in "${RESULTS_DIR}"/*.result; do
            [[ -f "$f" ]] || continue
            local gid p1 p2 outcome
            gid="$(basename "$f" .result)"
            read -r p1 p2 outcome <"$f"
            printf '%s,%s,%s,%s\n' "$gid" "$p1" "$p2" "$outcome"
        done
    } >"$games_csv"

    log "Standings CSV : $standings_csv"
    log "Games CSV     : $games_csv"
}

# ── main ─────────────────────────────────────────────────────────────────────

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

resolve_python
mkdir -p "$RESULTS_DIR" "$GAMES_DIR"

nc="${#CONTESTANTS[@]}"
(( nc >= 2 )) || die "Need at least 2 contestants. Edit CONTESTANTS in the script."

total_games=$(( TOURNAMENT_ITERATIONS * nc * (nc-1) / 2 * GAMES_PER_MATCH ))
start_ts="$(date +%s)"

echo ""
hr
echo "  SEQUENCE GAME AI TOURNAMENT"
hr
log "Contestants      : $nc"
local_c=""
for local_c in "${CONTESTANTS[@]}"; do log "                   · $local_c"; done
log "Iterations       : $TOURNAMENT_ITERATIONS"
log "Games / match    : $GAMES_PER_MATCH  (P1/P2 sides alternate each game)"
log "Max concurrent   : $MAX_CONCURRENT"
log "Max turns / game : $MAX_TURNS"
log "Temperature      : $TEMPERATURE"
log "Total games      : $total_games"
log "Python           : $PYTHON_CMD"
log "Output           : $LOG_DIR"
hr
echo ""

game_n=0

for (( iter=1; iter<=TOURNAMENT_ITERATIONS; iter++ )); do
    (( TOURNAMENT_ITERATIONS > 1 )) && log "── Iteration ${iter} / ${TOURNAMENT_ITERATIONS} ──"

    for (( i=0; i<nc; i++ )); do
        for (( j=i+1; j<nc; j++ )); do
            a="${CONTESTANTS[$i]}"
            b="${CONTESTANTS[$j]}"

            log "Match: ${a#*:}  vs  ${b#*:}  (${GAMES_PER_MATCH} games)"

            for (( g=1; g<=GAMES_PER_MATCH; g++ )); do
                (( game_n++ )) || true

                # Alternate who has first-move advantage
                if (( g % 2 == 1 )); then p1="$a"; p2="$b"
                else                       p1="$b"; p2="$a"; fi

                game_id="iter${iter}_${i}v${j}_g${g}"

                throttle
                log "  [${game_n}/${total_games}] ${game_id}: ${p1#*:} (P1) vs ${p2#*:} (P2)"
                run_game_bg "$p1" "$p2" "$game_id"
            done
        done
    done
done

echo ""
log "Waiting for the last ${#ACTIVE_PIDS[@]} game(s) to finish..."
wait_all

elapsed=$(( $(date +%s) - start_ts ))
log "All ${game_n} games done — ${elapsed}s  ($(( elapsed/60 ))m $(( elapsed%60 ))s)"

print_standings
print_head2head
save_csv

echo ""
log "Full logs: $LOG_DIR"
echo ""
hr
echo "  TOURNAMENT COMPLETE"
hr
echo ""
