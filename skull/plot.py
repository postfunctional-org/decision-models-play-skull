#!/usr/bin/env python3
"""Charts for a pile of Skull games. Every rate carries its interval.

On colour: the four seat colours cannot carry identity in a chart. Measured in
OKLab, OpenJev and LUNA separate by 9.2 and Jev and OpenJev by 12.0, against a
normal-vision floor of 15 -- they are three greens and an orange, chosen to read
apart on a dark table where each robot is also in a different place. So here the
axis label carries identity, every bar is directly labelled with its value, and
colour says one thing only: model or scripted bar.

Error bars are Wilson intervals on proportions and t intervals on means, which
is the whole reason to plot this rather than print it -- the interesting thing
about a four-player win rate is how wide it still is.

    python3 -m skull.plot games/list --out results/charts/list
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402

from skull.stats import gather, mean_ci, wilson       # noqa: E402
from skull.table import SEATS, seat                   # noqa: E402

INK, DIM, GRID = "#E8EDF2", "#9AA7B0", "#2A313A"
BG, PANEL = "#12161B", "#1A1F26"
MODEL, BAR = "#5BE9D0", "#7A8691"


def style(ax, title, sub):
    ax.set_facecolor(PANEL)
    ax.figure.set_facecolor(BG)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=DIM, length=0, labelsize=10)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=13, loc="left", pad=16, weight="bold")
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, color=DIM, fontsize=9,
                va="bottom")


def bars(ax, rows, pct=True, note=""):
    """rows: (label, value, lo, hi, n, is_model), already in the order wanted."""
    ys = range(len(rows))
    vals = [r[1] for r in rows]
    cols = [MODEL if r[5] else BAR for r in rows]
    err = [[max(0, r[1] - r[2]) for r in rows], [max(0, r[3] - r[1]) for r in rows]]
    ax.barh(list(ys), vals, color=cols, height=0.56, zorder=3)
    ax.errorbar(vals, list(ys), xerr=err, fmt="none", ecolor=INK, elinewidth=1.4,
                capsize=5, capthick=1.4, zorder=4, alpha=0.85)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in rows], color=INK, fontsize=11)
    ax.invert_yaxis()
    top = max((r[3] for r in rows), default=1) * 1.25 or 1
    ax.set_xlim(0, top)
    for y, r in zip(ys, rows):
        txt = f"{r[1]:.1%}" if pct else f"{r[1]:.2f}"
        ax.text(r[3] + top * 0.02, y, f"{txt}   n={r[4]}", color=DIM,
                fontsize=9, va="center")
    if pct:
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    if note:
        ax.text(0, -0.16, note, transform=ax.transAxes, color=DIM, fontsize=9,
                va="top", wrap=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Skull")
    a = ap.parse_args()
    d = gather(a.roots)
    S, out = d["seats"], Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = list(S)
    ism = {n: n in SEATS for n in names}
    shown = {n: seat(n)["shown"] for n in names}
    # the null is one in however many sit at a table, not one in every name seen
    per_game = 1.0 / 4

    def rows_for(k_key, n_key, pct=True):
        rs = []
        for n in names:
            s = S[n]
            k, t = s.get(k_key, 0), s.get(n_key, 0)
            lo, hi = wilson(k, t)
            rs.append((shown[n], (k / t if t else 0.0), lo, hi, t, ism[n]))
        return sorted(rs, key=lambda r: -r[1])

    # 1 -- the headline
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(names) + 2.6))
    bars(ax, rows_for("doomed", "bids"),
         note="A bid whose own mat holds a skull inside it. The challenger turns "
              "over their own mat first,\nso it cannot be made good -- wrong from "
              "that player's own information, before anything is turned.")
    style(ax, "Guaranteed-loss bids",
          f"{d['games']} games   ·   Wilson 95% intervals   ·   "
          "teal = model, grey = scripted bar")
    fig.tight_layout(); fig.savefig(out / "doomed_bids.png", dpi=150); plt.close(fig)

    # 2 -- challenges made good
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(names) + 2.6))
    bars(ax, rows_for("round_wins", "challenges"),
         note="Of the bids a seat ended up having to run, the share it made good.")
    style(ax, "Challenges made good",
          f"{d['games']} games   ·   Wilson 95% intervals")
    fig.tight_layout(); fig.savefig(out / "challenges.png", dpi=150); plt.close(fig)

    # 3 -- win rate, with the null drawn on it
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(names) + 2.8))
    bars(ax, rows_for("wins", "games"),
         note="The weakest measure here, and the reason the others exist: with "
              "four players the null is 25%,\nand separating 40% from chance "
              "takes about 50 games.")
    ax.axvline(per_game, color="#E8556D", lw=1.4, ls="--", zorder=5)
    ax.text(per_game, -0.7, f"  chance = {per_game:.0%}", color="#E8556D",
            fontsize=9, va="bottom")
    style(ax, "Games won", f"{d['games']} games   ·   Wilson 95% intervals")
    fig.tight_layout(); fig.savefig(out / "wins.png", dpi=150); plt.close(fig)

    # 4 -- discs lost, a mean rather than a proportion
    rs = []
    for n in names:
        xs = [float(x) for x in d["lost"].get(n, [])]
        m, lo, hi = mean_ci(xs)
        rs.append((shown[n], m, lo, hi, len(xs), ism[n]))
    rs.sort(key=lambda r: -r[1])
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(names) + 2.6))
    bars(ax, rs, pct=False,
         note="Discs forfeited per game, out of four. A failed challenge costs "
              "one.")
    style(ax, "Discs lost per game", f"{d['games']} games   ·   95% t intervals")
    fig.tight_layout(); fig.savefig(out / "discs_lost.png", dpi=150); plt.close(fig)

    print(f"wrote 4 charts to {out}")


if __name__ == "__main__":
    main()
