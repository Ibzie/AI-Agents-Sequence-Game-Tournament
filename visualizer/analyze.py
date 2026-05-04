#!/usr/bin/env python3
"""
AI vs AI Sequence Tournament — Deep Analyzer
Parses tournament text logs + structured JSON for research paper figures.
"""

import json, os, re, sys
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib.gridspec as gridspec

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
TOURN_DIR  = ROOT / "tournament_logs"
JSON_DIR   = Path(__file__).resolve().parent / "logs"
OUTPUT_DIR = Path(__file__).resolve().parent / "analysis_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── style ─────────────────────────────────────────────────────────────────────
DARK_BG   = "#16213e"
PANEL_BG  = "#1a1a2e"
BORDER    = "#444466"
C_GREY    = "#AAAAAA"
C_RED     = "#E05C5C"
C_AMBER   = "#F5A623"
C_BLUE    = "#4C8EDA"
C_GREEN   = "#50C878"
C_PURPLE  = "#9B59B6"
C_TEAL    = "#1ABC9C"

MODEL_COLOURS = {
    "granite4:3b":   C_TEAL,
    "ministral-3:3b": C_AMBER,
    "qwen3.5:4b":    C_BLUE,
    "gemma4:e4b":    C_PURPLE,
}

plt.rcParams.update({
    "axes.facecolor":   PANEL_BG,
    "figure.facecolor": DARK_BG,
    "axes.edgecolor":   BORDER,
    "axes.labelcolor":  "white",
    "xtick.color":      "white",
    "ytick.color":      "white",
    "text.color":       "white",
    "grid.color":       "#333355",
    "grid.linestyle":   "--",
    "grid.alpha":       0.5,
    "font.family":      "DejaVu Sans",
})

TS_FMT = "%Y-%m-%d %H:%M:%S,%f"

def ts(line):
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
    return datetime.strptime(m.group(1), TS_FMT) if m else None

def save(fig, name):
    p = OUTPUT_DIR / name
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {p}")


# ─────────────────────────────────────────────────────────────────────────────
# TEXT LOG PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_log(path: Path) -> dict:
    lines = path.read_text(errors="replace").splitlines()

    p_model   = {}          # pid → model
    moves     = []
    seq_snap  = []          # list of {turn, p1_seq, p2_seq}
    winner_id = winner_model = None
    total_turns = 0

    # per-move tracking
    cur_turn = cur_pid = None
    attempt_ts: dict = {}   # pid → timestamp of Attempt 1/3
    http_ts:    dict = {}   # pid → timestamp of HTTP 200
    pending_fallback = False
    pending_retries  = 0

    cur_p1_seq = cur_p2_seq = 0

    for line in lines:
        t = ts(line)

        # ── player metadata
        m = re.search(r"Player (\d): provider=\S+, model=(\S+)", line)
        if m:
            pid = "p" + m.group(1)
            p_model[pid] = m.group(2).rstrip(",")
            continue

        # ── turn header
        m = re.search(r"--- Turn (\d+): (p\d+)", line)
        if m:
            cur_turn = int(m.group(1))
            cur_pid  = m.group(2)
            pending_fallback = False
            pending_retries  = 0
            continue

        # ── attempt (track retries and timing)
        m = re.search(r"\[(p\d+)\] Attempt (\d+)/3", line)
        if m:
            pid, attempt_n = m.group(1), int(m.group(2))
            if attempt_n == 1:
                attempt_ts[pid] = t
            pending_retries = attempt_n - 1
            continue

        # ── HTTP response received
        if "HTTP Request: POST" in line and "200 OK" in line and cur_pid:
            http_ts[cur_pid] = t
            continue

        # ── fallback parsing
        if "Recovered move_index" in line or "fallback" in line.lower():
            pending_fallback = True
            continue

        # ── move played (authoritative record)
        m = re.search(
            r"(p\d+) plays: type=(\w+) card=(\w+) pos=\(?([\d-]+),\s*([\d-]+)\)?",
            line
        )
        if m:
            pid   = m.group(1)
            mtype = m.group(2)
            card  = m.group(3)
            row   = int(m.group(4))
            col   = int(m.group(5))

            duration = None
            if pid in attempt_ts and pid in http_ts and attempt_ts[pid] and http_ts[pid]:
                duration = (http_ts[pid] - attempt_ts[pid]).total_seconds()
                if duration < 0:
                    duration = None

            moves.append({
                "turn":     cur_turn,
                "player":   pid,
                "model":    p_model.get(pid, "?"),
                "type":     mtype,
                "card":     card,
                "position": (row, col),
                "duration": duration,
                "fallback": pending_fallback,
                "retries":  pending_retries,
            })
            pending_fallback = False
            pending_retries  = 0
            # clear used timestamps
            attempt_ts.pop(pid, None)
            http_ts.pop(pid, None)
            continue

        # ── sequence snapshot
        m = re.search(r"\s+(p\d+) sequences: (\d+)", line)
        if m:
            pid, n = m.group(1), int(m.group(2))
            if pid == "p1":
                cur_p1_seq = n
            else:
                cur_p2_seq = n
            # record after both updated (crude but works per-move)
            if moves and cur_turn == moves[-1]["turn"]:
                moves[-1]["seq_p1"] = cur_p1_seq
                moves[-1]["seq_p2"] = cur_p2_seq
            continue

        # ── winner / draw
        m = re.search(r"WINNER: (p\d+) \(([^)]+)\) in (\d+) turns", line)
        if m:
            winner_id    = m.group(1)
            winner_model = m.group(2)
            total_turns  = int(m.group(3))
            continue
        if re.search(r"DRAW after (\d+) turns", line):
            winner_id = "draw"
            total_turns = int(re.search(r"DRAW after (\d+) turns", line).group(1))
            continue

    return {
        "file":         path.name,
        "p1_model":     p_model.get("p1", "?"),
        "p2_model":     p_model.get("p2", "?"),
        "winner_id":    winner_id,
        "winner_model": winner_model,
        "total_turns":  total_turns,
        "moves":        moves,
    }


def load_tournament():
    """Find the most recent tournament run and parse all game logs."""
    runs = sorted(TOURN_DIR.glob("*/games"), reverse=True)
    if not runs:
        sys.exit("No tournament runs found under tournament_logs/")
    games_dir = runs[0]
    print(f"Loading tournament: {games_dir.parent.name}  ({len(list(games_dir.glob('*.log')))} logs)")
    games = [parse_log(p) for p in sorted(games_dir.glob("*.log"))]
    print(f"  Parsed {len(games)} games  ({sum(1 for g in games if g['winner_id'] not in (None,'draw'))} decisive)")
    return games


def load_json_games():
    """Load structured JSON game logs (token/timing data)."""
    jsons = []
    for p in sorted(JSON_DIR.glob("*.json")):
        with open(p) as f:
            jsons.append(json.load(f))
    return jsons


# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATE STATS
# ─────────────────────────────────────────────────────────────────────────────

def aggregate(games):
    """Build per-model statistics from all parsed games."""
    models = sorted(MODEL_COLOURS.keys())
    stats  = {m: defaultdict(list) for m in models}

    for g in games:
        p1m, p2m = g["p1_model"], g["p2_model"]
        wm = g["winner_model"]

        for m in (p1m, p2m):
            if m not in stats:
                continue
            stats[m]["games"].append(g)
            stats[m]["wins"].append(1 if m == wm else 0)
            stats[m]["total_turns"].append(g["total_turns"])

        role = {p1m: "p1", p2m: "p2"}
        moves = g["moves"]
        for mv in moves:
            mdl = mv["model"]
            if mdl not in stats:
                continue
            stats[mdl]["moves"].append(mv)
            stats[mdl]["move_types"].append(mv["type"])
            stats[mdl]["positions"].append(mv["position"])
            if mv["duration"] is not None:
                stats[mdl]["durations"].append(mv["duration"])
            stats[mdl]["fallbacks"].append(1 if mv["fallback"] else 0)
            stats[mdl]["retries"].append(mv["retries"])

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# CHART 01 — Win rates
# ─────────────────────────────────────────────────────────────────────────────

def chart_win_rates(games):
    wins  = Counter(g["winner_model"] for g in games if g["winner_id"] != "draw")
    total = Counter()
    for g in games:
        total[g["p1_model"]] += 1
        total[g["p2_model"]] += 1

    models  = sorted(MODEL_COLOURS, key=lambda m: -wins.get(m, 0))
    pcts    = [wins.get(m, 0) / total[m] * 100 for m in models]
    colours = [MODEL_COLOURS[m] for m in models]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar([m.split(":")[0] for m in models], pcts,
                  color=colours, width=0.55, edgecolor="white", linewidth=0.8)
    for bar, m, pct in zip(bars, models, pcts):
        w, tot = wins.get(m, 0), total[m]
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2,
                f"{w}/{tot}\n({pct:.0f}%)", ha="center", va="bottom",
                fontsize=10, fontweight="bold", color="white")
    ax.axhline(50, color=C_GREY, linewidth=0.9, linestyle="--", alpha=0.6)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Win Rate (%)", fontsize=11)
    ax.set_title("Overall Win Rate by Model  (36 games, 2×round-robin BO3)",
                 fontsize=12, fontweight="bold", pad=12)
    save(fig, "01_win_rates.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 02 — Head-to-head heatmap
# ─────────────────────────────────────────────────────────────────────────────

def chart_h2h(games):
    models = sorted(MODEL_COLOURS.keys())
    n      = len(models)
    idx    = {m: i for i, m in enumerate(models)}

    wins = np.zeros((n, n))  # wins[row][col] = row beat col N times
    played = np.zeros((n, n))

    for g in games:
        if g["winner_id"] == "draw":
            continue
        w, l = g["winner_model"], (g["p2_model"] if g["winner_model"] == g["p1_model"]
                                   else g["p1_model"])
        # find loser
        l = g["p2_model"] if g["winner_model"] == g["p1_model"] else g["p1_model"]
        if w in idx and l in idx:
            wins[idx[w]][idx[l]] += 1
            played[idx[w]][idx[l]] += 1
            played[idx[l]][idx[w]] += 1

    labels = [m.split(":")[0] for m in models]
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = LinearSegmentedColormap.from_list("", [PANEL_BG, C_AMBER])
    im = ax.imshow(wins, cmap=cmap, vmin=0, vmax=6)

    for i in range(n):
        for j in range(n):
            if i == j:
                ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1,
                             color="#333355", zorder=2))
                ax.text(j, i, "—", ha="center", va="center",
                        fontsize=13, color=C_GREY, zorder=3)
            else:
                total_ij = int(wins[i][j] + wins[j][i])
                txt = f"{int(wins[i][j])}/{total_ij}" if total_ij else "0"
                colour = "white" if wins[i][j] > 3 else C_GREY
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=11, fontweight="bold", color=colour, zorder=3)

    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(labels, fontsize=9, rotation=20, ha="right")
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Opponent (column)", fontsize=10)
    ax.set_ylabel("Model (row) — wins / games played", fontsize=10)
    ax.set_title("Head-to-Head Win Matrix\n(cell = row's wins / total games vs column)",
                 fontsize=11, fontweight="bold")
    plt.colorbar(im, ax=ax, fraction=0.04, label="Wins")
    plt.tight_layout()
    save(fig, "02_head_to_head.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 03 — Sabotage rate  (one_eyed_jack / total moves)
# ─────────────────────────────────────────────────────────────────────────────

def chart_sabotage(stats):
    models  = sorted(MODEL_COLOURS.keys(), key=lambda m: -sum(
        1 for mv in stats[m]["moves"] if mv["type"] == "one_eyed_jack") /
        max(len(stats[m]["moves"]), 1))
    labels  = [m.split(":")[0] for m in models]
    colours = [MODEL_COLOURS[m] for m in models]

    sab_rates = []
    wild_rates = []
    for m in models:
        mvs = stats[m]["moves"]
        n   = len(mvs)
        sab_rates.append(sum(1 for mv in mvs if mv["type"] == "one_eyed_jack") / n * 100)
        wild_rates.append(sum(1 for mv in mvs if mv["type"] == "two_eyed_jack") / n * 100)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # left — sabotage rate bar
    ax = axes[0]
    bars = ax.bar(labels, sab_rates, color=colours, width=0.55,
                  edgecolor="white", linewidth=0.8)
    for bar, r in zip(bars, sab_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{r:.1f}%", ha="center", va="bottom", fontsize=11,
                fontweight="bold", color="white")
    ax.set_ylabel("% of moves", fontsize=11)
    ax.set_title("Sabotage Rate\n(one-eyed jack: remove opponent chip)", fontsize=11, fontweight="bold")

    # right — wild jack rate bar
    ax2 = axes[1]
    bars2 = ax2.bar(labels, wild_rates, color=colours, width=0.55,
                    edgecolor="white", linewidth=0.8)
    for bar, r in zip(bars2, wild_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                 f"{r:.1f}%", ha="center", va="bottom", fontsize=11,
                 fontweight="bold", color="white")
    ax2.set_ylabel("% of moves", fontsize=11)
    ax2.set_title("Wild Jack Rate\n(two-eyed jack: place anywhere)", fontsize=11, fontweight="bold")

    fig.suptitle("Jack Card Usage Rates by Model", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "03_sabotage_rates.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 04 — Sabotage: winners vs losers
# ─────────────────────────────────────────────────────────────────────────────

def chart_sabotage_outcome(games):
    """Compare sabotage rate for the winner vs loser in each game."""
    w_sab, l_sab = [], []

    for g in games:
        if g["winner_id"] in (None, "draw"):
            continue
        winner_pid = g["winner_id"]
        loser_pid  = "p2" if winner_pid == "p1" else "p1"
        w_mvs = [mv for mv in g["moves"] if mv["player"] == winner_pid]
        l_mvs = [mv for mv in g["moves"] if mv["player"] == loser_pid]
        if w_mvs:
            w_sab.append(sum(1 for mv in w_mvs if mv["type"] == "one_eyed_jack") / len(w_mvs) * 100)
        if l_mvs:
            l_sab.append(sum(1 for mv in l_mvs if mv["type"] == "one_eyed_jack") / len(l_mvs) * 100)

    fig, ax = plt.subplots(figsize=(7, 5))
    data   = [w_sab, l_sab]
    labels = ["Winner", "Loser"]
    cols   = [C_GREEN, C_RED]

    parts = ax.violinplot(data, positions=[1, 2], showmedians=True, showextrema=True)
    for body, col in zip(parts["bodies"], cols):
        body.set_facecolor(col); body.set_alpha(0.65)
    parts["cmedians"].set_color("white"); parts["cmedians"].set_linewidth(2)
    for k in ("cbars", "cmaxes", "cmins"):
        parts[k].set_color("white"); parts[k].set_linewidth(1)

    for i, (d, col) in enumerate(zip(data, cols)):
        ax.scatter([i+1]*len(d), d, color=col, alpha=0.5, s=20, zorder=3)
        ax.text(i+1, np.mean(d) + 0.3, f"μ={np.mean(d):.1f}%",
                ha="center", fontsize=10, fontweight="bold", color=col)

    ax.set_xticks([1, 2]); ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylabel("Sabotage rate (%)", fontsize=11)
    ax.set_title("Sabotage Rate: Winners vs Losers\n(one-eyed jack plays / total moves)",
                 fontsize=12, fontweight="bold")
    save(fig, "04_sabotage_vs_outcome.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 05 — Sabotage timing (what turn do models sabotage?)
# ─────────────────────────────────────────────────────────────────────────────

def chart_sabotage_timing(stats):
    fig, ax = plt.subplots(figsize=(11, 5))

    for m, col in MODEL_COLOURS.items():
        sab_turns = [mv["turn"] for mv in stats[m]["moves"] if mv["type"] == "one_eyed_jack"]
        if not sab_turns:
            continue
        ax.scatter(sab_turns, [m.split(":")[0]] * len(sab_turns),
                   color=col, alpha=0.7, s=60, zorder=3,
                   label=f"{m.split(':')[0]}  (n={len(sab_turns)})")

    ax.set_xlabel("Turn number", fontsize=11)
    ax.set_title("Sabotage Move Timing — When Do Models Strike?",
                 fontsize=12, fontweight="bold", pad=12)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(axis="x", alpha=0.4)
    save(fig, "05_sabotage_timing.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 06 — Fallback parsing rate
# ─────────────────────────────────────────────────────────────────────────────

def chart_fallback(stats):
    models  = sorted(MODEL_COLOURS.keys())
    labels  = [m.split(":")[0] for m in models]
    colours = [MODEL_COLOURS[m] for m in models]

    fb_rates  = [np.mean(stats[m]["fallbacks"]) * 100 for m in models]
    retry_avg = [np.mean(stats[m]["retries"]) for m in models]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    ax = axes[0]
    bars = ax.bar(labels, fb_rates, color=colours, width=0.55, edgecolor="white", linewidth=0.8)
    for bar, r in zip(bars, fb_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"{r:.1f}%", ha="center", va="bottom", fontsize=11,
                fontweight="bold", color="white")
    ax.set_ylabel("% of moves needing fallback", fontsize=10)
    ax.set_title("Response Fallback Rate\n(model output required regex/number extraction)", fontsize=10, fontweight="bold")

    ax2 = axes[1]
    bars2 = ax2.bar(labels, retry_avg, color=colours, width=0.55, edgecolor="white", linewidth=0.8)
    for bar, r in zip(bars2, retry_avg):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f"{r:.3f}", ha="center", va="bottom", fontsize=11,
                 fontweight="bold", color="white")
    ax2.set_ylabel("Avg retries per move", fontsize=10)
    ax2.set_title("Average Retry Attempts per Move\n(max 3 attempts per move)", fontsize=10, fontweight="bold")

    fig.suptitle("Model Response Reliability", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "06_fallback_reliability.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 07 — Move timing (from timestamps)
# ─────────────────────────────────────────────────────────────────────────────

def chart_move_timing(stats):
    models  = [m for m in sorted(MODEL_COLOURS) if stats[m]["durations"]]
    labels  = [m.split(":")[0] for m in models]
    colours = [MODEL_COLOURS[m] for m in models]
    data    = [stats[m]["durations"] for m in models]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # violin
    ax = axes[0]
    parts = ax.violinplot(data, positions=range(1, len(models)+1),
                          showmedians=True, showextrema=True)
    for body, col in zip(parts["bodies"], colours):
        body.set_facecolor(col); body.set_alpha(0.7)
    parts["cmedians"].set_color("white"); parts["cmedians"].set_linewidth(2)
    for k in ("cbars", "cmaxes", "cmins"):
        parts[k].set_color("white"); parts[k].set_linewidth(1)

    for i, (d, col) in enumerate(zip(data, colours)):
        ax.text(i+1, np.mean(d) + 0.3, f"μ={np.mean(d):.1f}s",
                ha="center", fontsize=9, fontweight="bold", color=col)

    ax.set_xticks(range(1, len(models)+1))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Seconds (LLM request → response)", fontsize=10)
    ax.set_title("Move Duration Distribution", fontsize=11, fontweight="bold")

    # bar of totals
    ax2 = axes[1]
    total_mins = [sum(stats[m]["durations"]) / 60 for m in models]
    bars = ax2.bar(labels, total_mins, color=colours, width=0.55,
                   edgecolor="white", linewidth=0.8)
    for bar, mins, m in zip(bars, total_mins, models):
        n = len(stats[m]["durations"])
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{mins:.0f} min\n({n} moves)", ha="center", va="bottom",
                 fontsize=9, fontweight="bold", color="white")
    ax2.set_ylabel("Total thinking time (minutes)", fontsize=10)
    ax2.set_title("Total LLM Time Across Tournament", fontsize=11, fontweight="bold")

    fig.suptitle("Move Timing by Model", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "07_move_timing.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 08 — Board heatmaps per model
# ─────────────────────────────────────────────────────────────────────────────

def chart_heatmaps(stats):
    models  = sorted(MODEL_COLOURS.keys())
    fig, axes = plt.subplots(1, len(models), figsize=(15, 4.5))

    for ax, m in zip(axes, models):
        col   = MODEL_COLOURS[m]
        grid  = np.zeros((10, 10))
        for (r, c) in stats[m]["positions"]:
            if 0 <= r < 10 and 0 <= c < 10:
                grid[r][c] += 1

        cmap = LinearSegmentedColormap.from_list("", [PANEL_BG, col])
        im = ax.imshow(grid, cmap=cmap, aspect="equal", interpolation="nearest")
        for cr, cc in [(0,0),(0,9),(9,0),(9,9)]:
            ax.add_patch(plt.Rectangle((cc-0.5, cr-0.5), 1, 1,
                         color="#FFD700", alpha=0.4, zorder=2))
        ax.set_title(m.split(":")[0], fontsize=10, fontweight="bold", color=col)
        ax.set_xticks([]); ax.set_yticks([])
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.yaxis.set_tick_params(color="white")

    fig.suptitle("Aggregate Chip Placement Heatmap per Model  (all 36 games, gold=wildcards)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    save(fig, "08_board_heatmaps.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 09 — Board zone preference (edge / centre / corner area)
# ─────────────────────────────────────────────────────────────────────────────

def zone(r, c):
    if (r in (0, 9)) or (c in (0, 9)):
        return "edge"
    if 2 <= r <= 7 and 2 <= c <= 7:
        return "centre"
    return "near-edge"

def chart_zones(stats):
    models = sorted(MODEL_COLOURS.keys())
    zones  = ["edge", "near-edge", "centre"]
    z_cols = [C_RED, C_AMBER, C_TEAL]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(models))
    w = 0.25

    for zi, (z, zc) in enumerate(zip(zones, z_cols)):
        rates = []
        for m in models:
            pos = stats[m]["positions"]
            rates.append(sum(1 for r, c in pos if zone(r, c) == z) / max(len(pos), 1) * 100)
        bars = ax.bar(x + zi*w, rates, width=w, color=zc, alpha=0.85,
                      label=z, edgecolor="white", linewidth=0.6)

    ax.set_xticks(x + w); ax.set_xticklabels([m.split(":")[0] for m in models], fontsize=10)
    ax.set_ylabel("% of placements", fontsize=11)
    ax.set_title("Board Zone Preference per Model\n(edge = row/col 0 or 9, centre = rows/cols 2–7)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=10)
    save(fig, "09_board_zones.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 10 — Win rate as P1 vs P2 (first-move advantage)
# ─────────────────────────────────────────────────────────────────────────────

def chart_position_winrate(games):
    models = sorted(MODEL_COLOURS.keys())
    p1_wr  = defaultdict(lambda: [0, 0])   # model → [wins_as_p1, games_as_p1]
    p2_wr  = defaultdict(lambda: [0, 0])

    for g in games:
        if g["winner_id"] == "draw":
            continue
        wm = g["winner_model"]
        for role, mdl in (("p1", g["p1_model"]), ("p2", g["p2_model"])):
            if mdl not in MODEL_COLOURS:
                continue
            bucket = p1_wr[mdl] if role == "p1" else p2_wr[mdl]
            bucket[1] += 1
            if mdl == wm:
                bucket[0] += 1

    labels = [m.split(":")[0] for m in models]
    x = np.arange(len(models))
    w = 0.35

    p1_pcts = [p1_wr[m][0]/max(p1_wr[m][1],1)*100 for m in models]
    p2_pcts = [p2_wr[m][0]/max(p2_wr[m][1],1)*100 for m in models]

    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - w/2, p1_pcts, width=w, color=C_BLUE,   alpha=0.85, label="As Player 1 (first move)", edgecolor="white", linewidth=0.7)
    b2 = ax.bar(x + w/2, p2_pcts, width=w, color=C_PURPLE, alpha=0.85, label="As Player 2", edgecolor="white", linewidth=0.7)

    for bar, pct, m in zip(b1, p1_pcts, models):
        n = p1_wr[m][1]
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                f"{pct:.0f}%\n(n={n})", ha="center", va="bottom", fontsize=8, color=C_BLUE)
    for bar, pct, m in zip(b2, p2_pcts, models):
        n = p2_wr[m][1]
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                f"{pct:.0f}%\n(n={n})", ha="center", va="bottom", fontsize=8, color=C_PURPLE)

    ax.axhline(50, color=C_GREY, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Win rate (%)", fontsize=11)
    ax.set_title("Win Rate by Board Position (P1 vs P2)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    save(fig, "10_position_winrate.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 11 — Game length distribution
# ─────────────────────────────────────────────────────────────────────────────

def chart_game_lengths(games, stats):
    models  = sorted(MODEL_COLOURS.keys())
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Per winner model box
    ax = axes[0]
    data = [[g["total_turns"] for g in games if g["winner_model"] == m] for m in models]
    labels = [m.split(":")[0] for m in models]
    parts = ax.violinplot([d for d in data if d],
                          positions=[i+1 for i,d in enumerate(data) if d],
                          showmedians=True)
    for body, m in zip(parts["bodies"],
                       [m for m, d in zip(models, data) if d]):
        body.set_facecolor(MODEL_COLOURS[m]); body.set_alpha(0.7)
    parts["cmedians"].set_color("white"); parts["cmedians"].set_linewidth(2)
    for k in ("cbars","cmaxes","cmins"):
        parts[k].set_color("white")
    ticks = [i+1 for i,d in enumerate(data) if d]
    tick_labels = [l for l,d in zip(labels, data) if d]
    ax.set_xticks(ticks); ax.set_xticklabels(tick_labels, fontsize=9)
    ax.set_ylabel("Total moves", fontsize=10)
    ax.set_title("Game Length Distribution\n(grouped by winner)", fontsize=10, fontweight="bold")

    # Overall histogram
    ax2 = axes[1]
    all_lengths = [g["total_turns"] for g in games if g["total_turns"] > 0]
    ax2.hist(all_lengths, bins=15, color=C_TEAL, edgecolor="white",
             alpha=0.8, linewidth=0.7)
    ax2.axvline(np.mean(all_lengths), color=C_AMBER, linewidth=2,
                linestyle="--", label=f"Mean = {np.mean(all_lengths):.0f}")
    ax2.axvline(np.median(all_lengths), color=C_RED, linewidth=2,
                linestyle=":", label=f"Median = {np.median(all_lengths):.0f}")
    ax2.set_xlabel("Total moves", fontsize=10)
    ax2.set_ylabel("# games", fontsize=10)
    ax2.set_title("Game Length Distribution (all 36 games)", fontsize=10, fontweight="bold")
    ax2.legend(fontsize=9)

    fig.suptitle("Game Length Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "11_game_lengths.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 12 — Sequence formation speed
# ─────────────────────────────────────────────────────────────────────────────

def chart_seq_speed(games):
    """When does each model achieve its first sequence?"""
    first_seq = defaultdict(list)   # model → list of turns

    for g in games:
        pid_model = {"p1": g["p1_model"], "p2": g["p2_model"]}
        achieved  = {"p1": False, "p2": False}

        for mv in g["moves"]:
            pid = mv["player"]
            if achieved[pid]:
                continue
            seq_self = mv.get("seq_p1") if pid == "p1" else mv.get("seq_p2")
            if seq_self and seq_self >= 1:
                mdl = pid_model[pid]
                if mdl in MODEL_COLOURS:
                    first_seq[mdl].append(mv["turn"])
                achieved[pid] = True

    models  = sorted(MODEL_COLOURS.keys())
    labels  = [m.split(":")[0] for m in models]
    colours = [MODEL_COLOURS[m] for m in models]
    data    = [first_seq.get(m, []) for m in models]

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (d, col, lbl) in enumerate(zip(data, colours, labels)):
        if d:
            ax.scatter([i+1]*len(d), d, color=col, alpha=0.6, s=40, zorder=3)
            ax.plot([i+0.7, i+1.3], [np.mean(d)]*2, color=col, linewidth=3, zorder=4)
            ax.text(i+1, np.mean(d)+0.8, f"μ={np.mean(d):.0f}", ha="center",
                    fontsize=9, fontweight="bold", color=col)

    ax.set_xticks(range(1, len(models)+1))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Turn of first sequence", fontsize=11)
    ax.set_title("First Sequence Formation Speed by Model\n(lower = faster sequence completion)",
                 fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.4)
    save(fig, "12_sequence_speed.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 13 — Jack usage full breakdown stacked bar
# ─────────────────────────────────────────────────────────────────────────────

def chart_jack_breakdown(stats):
    models  = sorted(MODEL_COLOURS.keys(), key=lambda m: -len(stats[m]["moves"]))
    labels  = [m.split(":")[0] for m in models]
    colours = [MODEL_COLOURS[m] for m in models]

    place_r = []; sab_r = []; wild_r = []
    for m in models:
        mvs = stats[m]["moves"]; n = max(len(mvs), 1)
        place_r.append(sum(1 for mv in mvs if mv["type"] == "place")       / n * 100)
        sab_r.append(  sum(1 for mv in mvs if mv["type"] == "one_eyed_jack") / n * 100)
        wild_r.append( sum(1 for mv in mvs if mv["type"] == "two_eyed_jack") / n * 100)

    x = np.arange(len(models))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, place_r, color=C_TEAL,   alpha=0.85, label="Normal place",      edgecolor="white", linewidth=0.7)
    ax.bar(x, sab_r,   bottom=place_r, color=C_RED,   alpha=0.85, label="One-eyed jack (sabotage)", edgecolor="white", linewidth=0.7)
    ax.bar(x, wild_r,  bottom=[p+s for p,s in zip(place_r, sab_r)],
           color=C_AMBER, alpha=0.85, label="Two-eyed jack (wild)", edgecolor="white", linewidth=0.7)

    for i, (p, s, w) in enumerate(zip(place_r, sab_r, wild_r)):
        ax.text(i, 50, f"{p:.0f}%", ha="center", va="center",
                fontsize=9, fontweight="bold", color="white")
        if s > 0.5:
            ax.text(i, p + s/2, f"{s:.1f}%", ha="center", va="center",
                    fontsize=8, color="white")
        if w > 0.5:
            ax.text(i, p + s + w/2, f"{w:.1f}%", ha="center", va="center",
                    fontsize=8, color="white")

    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 105)
    ax.set_ylabel("% of all moves", fontsize=11)
    ax.set_title("Move Type Breakdown per Model", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10, loc="upper right")
    save(fig, "13_move_type_breakdown.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 14 — Token deep-dive from JSON log (fe01464e)
# ─────────────────────────────────────────────────────────────────────────────

def chart_token_deep_dive(json_games):
    if not json_games:
        print("  (no JSON game logs found, skipping token deep-dive)")
        return

    # pick the game with token data
    g = next((x for x in json_games
               if any("prompt_tokens" in e for e in x.get("events", []))), None)
    if not g:
        print("  (no JSON game with token data, skipping)")
        return

    moves = [e for e in g["events"] if e["type"] == "move" and "prompt_tokens" in e]
    p_info = {p["id"]: p["model"] for p in g["players"]}

    fig = plt.figure(figsize=(14, 10))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    # ── top-left: prompt tokens over time per player
    ax1 = fig.add_subplot(gs[0, 0])
    for pid in ("player1", "player2"):
        pm    = sorted([e for e in moves if e["player"] == pid], key=lambda x: x["turn"])
        model = p_info.get(pid, pid)
        col   = MODEL_COLOURS.get(model, C_GREY)
        turns = [e["turn"] for e in pm]
        ptoks = [e["prompt_tokens"] for e in pm]
        ax1.plot(turns, ptoks, color=col, linewidth=1.5, label=model.split(":")[0])
        ax1.fill_between(turns, ptoks, alpha=0.15, color=col)
    ax1.set_xlabel("Turn"); ax1.set_ylabel("Prompt tokens")
    ax1.set_title("Prompt Token Growth Over Game", fontsize=10, fontweight="bold")
    ax1.legend(fontsize=8)

    # ── top-right: completion tokens (capped at 1024?)
    ax2 = fig.add_subplot(gs[0, 1])
    for pid in ("player1", "player2"):
        pm    = sorted([e for e in moves if e["player"] == pid], key=lambda x: x["turn"])
        model = p_info.get(pid, pid)
        col   = MODEL_COLOURS.get(model, C_GREY)
        turns = [e["turn"] for e in pm]
        ctoks = [e["completion_tokens"] for e in pm]
        ax2.plot(turns, ctoks, color=col, linewidth=1.5, label=model.split(":")[0])
        pct_cap = sum(1 for c in ctoks if c >= 1024) / len(ctoks) * 100
        ax2.text(turns[-1], ctoks[-1], f" {pct_cap:.0f}% at cap", fontsize=7, color=col, va="center")
    ax2.axhline(1024, color=C_RED, linewidth=0.9, linestyle=":", alpha=0.7, label="1024 cap")
    ax2.set_xlabel("Turn"); ax2.set_ylabel("Completion tokens")
    ax2.set_title("Completion Tokens (1024 = context cap)", fontsize=10, fontweight="bold")
    ax2.legend(fontsize=8)

    # ── bottom-left: duration violin
    ax3 = fig.add_subplot(gs[1, 0])
    dur_data, dur_labels, dur_cols = [], [], []
    for pid in ("player1", "player2"):
        pm    = [e for e in moves if e["player"] == pid and "move_duration_seconds" in e]
        model = p_info.get(pid, pid)
        col   = MODEL_COLOURS.get(model, C_GREY)
        durs  = [e["move_duration_seconds"] for e in pm]
        if durs:
            dur_data.append(durs); dur_labels.append(model.split(":")[0]); dur_cols.append(col)
    if dur_data:
        parts = ax3.violinplot(dur_data, positions=range(1, len(dur_data)+1),
                               showmedians=True)
        for body, col in zip(parts["bodies"], dur_cols):
            body.set_facecolor(col); body.set_alpha(0.7)
        parts["cmedians"].set_color("white"); parts["cmedians"].set_linewidth(2)
        for k in ("cbars","cmaxes","cmins"):
            parts[k].set_color("white")
        ax3.set_xticks(range(1, len(dur_data)+1))
        ax3.set_xticklabels(dur_labels, fontsize=9)
        for i, (d, col) in enumerate(zip(dur_data, dur_cols)):
            ax3.text(i+1, np.mean(d)+0.3, f"μ={np.mean(d):.1f}s",
                     ha="center", fontsize=9, color=col, fontweight="bold")
    ax3.set_ylabel("Seconds"); ax3.set_title("Move Duration (structured log)", fontsize=10, fontweight="bold")

    # ── bottom-right: total token spend bar
    ax4 = fig.add_subplot(gs[1, 1])
    bar_labels, p_tots, c_tots, bar_cols = [], [], [], []
    for pid in ("player1", "player2"):
        pm    = [e for e in moves if e["player"] == pid]
        model = p_info.get(pid, pid)
        col   = MODEL_COLOURS.get(model, C_GREY)
        bar_labels.append(model.split(":")[0])
        p_tots.append(sum(e["prompt_tokens"] for e in pm))
        c_tots.append(sum(e["completion_tokens"] for e in pm))
        bar_cols.append(col)

    x = np.arange(len(bar_labels))
    ax4.bar(x, p_tots, color=bar_cols, alpha=0.9, label="Prompt", edgecolor="white", linewidth=0.7)
    ax4.bar(x, c_tots, bottom=p_tots, color=C_GREY, alpha=0.7, label="Completion", edgecolor="white", linewidth=0.7)
    for i, (pt, ct) in enumerate(zip(p_tots, c_tots)):
        ax4.text(i, pt+ct+200, f"{pt+ct:,}", ha="center", va="bottom",
                 fontsize=9, fontweight="bold", color="white")
    ax4.set_xticks(x); ax4.set_xticklabels(bar_labels, fontsize=9)
    ax4.set_ylabel("Total tokens"); ax4.set_title("Token Spend (one game)", fontsize=10, fontweight="bold")
    ax4.legend(fontsize=8)

    fig.suptitle(f"Token Deep-Dive — Structured Log (game: {g.get('game_id','?')})",
                 fontsize=13, fontweight="bold")
    save(fig, "14_token_deep_dive.png")


# ─────────────────────────────────────────────────────────────────────────────
# TEXT REPORT
# ─────────────────────────────────────────────────────────────────────────────

def print_report(games, stats):
    sep = "=" * 70
    print(f"\n{sep}")
    print("  AI vs AI SEQUENCE TOURNAMENT — ANALYSIS REPORT")
    print(sep)

    # ── Overall
    wins  = Counter(g["winner_model"] for g in games if g["winner_id"] not in (None, "draw"))
    total = Counter()
    for g in games:
        total[g["p1_model"]] += 1
        total[g["p2_model"]] += 1

    print("\n── STANDINGS ──────────────────────────────────────────────────────")
    print(f"  {'Model':<22}  {'W':>4}  {'L':>4}  {'Win%':>6}  {'Sab%':>6}  {'Fallback%':>10}  {'μ dur':>7}")
    print("  " + "-"*68)
    for m in sorted(MODEL_COLOURS, key=lambda m: -wins.get(m,0)):
        n   = total[m]
        w   = wins.get(m, 0)
        mvs = stats[m]["moves"]
        nm  = max(len(mvs), 1)
        sab = sum(1 for mv in mvs if mv["type"] == "one_eyed_jack") / nm * 100
        fb  = np.mean(stats[m]["fallbacks"]) * 100 if stats[m]["fallbacks"] else 0
        dur = np.mean(stats[m]["durations"]) if stats[m]["durations"] else 0
        print(f"  {m:<22}  {w:>4}  {n-w:>4}  {w/n*100:>5.0f}%  {sab:>5.1f}%  {fb:>9.1f}%  {dur:>6.1f}s")

    print("\n── JACK USAGE DETAIL ──────────────────────────────────────────────")
    for m in sorted(MODEL_COLOURS):
        mvs = stats[m]["moves"]; nm = max(len(mvs), 1)
        oe  = sum(1 for mv in mvs if mv["type"] == "one_eyed_jack")
        te  = sum(1 for mv in mvs if mv["type"] == "two_eyed_jack")
        pl  = sum(1 for mv in mvs if mv["type"] == "place")
        print(f"  {m:<22}  place={pl} ({pl/nm*100:.0f}%)  "
              f"sabotage={oe} ({oe/nm*100:.1f}%)  wild={te} ({te/nm*100:.1f}%)")

    print("\n── GAME LENGTHS ───────────────────────────────────────────────────")
    lengths = [g["total_turns"] for g in games if g["total_turns"] > 0]
    print(f"  mean={np.mean(lengths):.1f}  median={np.median(lengths):.0f}  "
          f"min={min(lengths)}  max={max(lengths)}")

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    games      = load_tournament()
    json_games = load_json_games()
    stats      = aggregate(games)

    print("\nGenerating charts...")
    chart_win_rates(games)
    chart_h2h(games)
    chart_sabotage(stats)
    chart_sabotage_outcome(games)
    chart_sabotage_timing(stats)
    chart_fallback(stats)
    chart_move_timing(stats)
    chart_heatmaps(stats)
    chart_zones(stats)
    chart_position_winrate(games)
    chart_game_lengths(games, stats)
    chart_seq_speed(games)
    chart_jack_breakdown(stats)
    chart_token_deep_dive(json_games)

    print_report(games, stats)
    print(f"All output saved to: {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
