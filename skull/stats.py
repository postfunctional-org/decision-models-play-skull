#!/usr/bin/env python3
"""What a pile of Skull transcripts says, with intervals on everything.

Win rate is the weakest thing here and it is reported last. Four players means
a null of 25%, and separating a 40% player from chance needs about 50 games --
at 20 games the interval on 40% is [0.22, 0.61], which excludes nothing. Games
are expensive; decisions are not. Every game yields roughly 150 of them, so the
per-decision rates below reach usable intervals an order of magnitude sooner.

The headline measure is one that needs no solver and no equilibrium:

    a bid is a GUARANTEED LOSS when the player's own mat holds a skull within
    the first `bid` discs from the top. The challenger turns over their own mat
    first, so such a bid cannot be made good, whatever anyone else is holding.
    It is wrong from information the player alone has, and it is wrong before
    any card is turned.

That makes it a blunder in the strict sense. The random bar makes it on about a
quarter of its claims. The `house` bar never made it in the recorded games, but
it also never claimed with its own skull down, so that zero says little.

    python3 -m skull.stats games/list --out results/stats_list.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
from pathlib import Path

from skull.game import SKULL, Skull


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def mean_ci(xs: list[float], z: float = 1.96) -> tuple[float, float, float]:
    n = len(xs)
    if not n:
        return 0.0, 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = z * sd / math.sqrt(n)
    return m, m - h, m + h


def safe_depth(mat: list[str]) -> int:
    """Discs you can turn over from your own mat, top down, before your skull."""
    n = 0
    for d in reversed(mat):
        if d == SKULL:
            break
        n += 1
    return n


def walk(t: dict) -> list[dict]:
    """Replay a transcript and hand back every real decision with its context."""
    # the shape has to come back with the transcript or the replay desyncs:
    # a binary game asks a different sequence of questions entirely
    g = Skull(names=list(t["names"]), seed=t["seed"], shape=t.get("shape", "list"))
    out = []
    for choice in t["answers"]:
        q = g.question()
        if q is None:
            break
        if "forced" not in q:
            seat = g.seats[q["seat"]]
            out.append({
                "who": q["who"], "kind": q["kind"], "choice": choice,
                "options": q["options"], "round": g.round_no,
                "mat": list(seat.mat), "hand": list(seat.hand),
                "safe": safe_depth(seat.mat),
                "own_skull": SKULL in seat.mat,
                "table": g.on_table(), "bid": g.bid,
                # in the binary shape the number is not in the choice: the
                # player settles on whatever rung the ladder is standing on
                "building": q.get("building"),
            })
        g.answer(choice)
    return out


def gather(roots: list[str]) -> dict:
    files = [f for r in roots for f in sorted(glob.glob(str(Path(r) / "*.json")))
             if Path(f).name != "stats.json"]
    seats = collections.defaultdict(lambda: collections.Counter())
    per_game = collections.defaultdict(list)
    ends = collections.Counter()
    games = 0
    for f in files:
        try:
            t = json.loads(Path(f).read_text())
        except Exception:
            continue
        if not t.get("names") or "answers" not in t:
            continue
        games += 1
        for e in t.get("log", []):
            if e["kind"] == "wins_game":
                ends[e.get("how", "?")] += 1
        for n in t["names"]:
            s = seats[n]
            s["games"] += 1
            s["wins"] += (t.get("winner") == n)
            s["points"] += t.get("points", {}).get(n, 0)
            per_game[n].append(4 - t.get("discs", {}).get(n, 4))
        for e in t.get("log", []):
            w = e.get("who")
            if not w:
                continue
            if e["kind"] == "challenge":
                seats[w]["challenges"] += 1
            elif e["kind"] == "wins_round":
                seats[w]["round_wins"] += 1
            elif e["kind"] == "fails":
                seats[w]["fails"] += 1
                if e.get("skull_of") == w:
                    seats[w]["self_skull"] += 1
            elif e["kind"] == "eliminated":
                seats[w]["eliminated"] += 1
        for d in walk(t):
            s = seats[d["who"]]
            s["decisions"] += 1
            committed = None
            if d["kind"] in ("open", "reply") and d["choice"].isdigit():
                committed = int(d["choice"])
            elif d["kind"] == "raise_to" and d["choice"] == "commit":
                committed = d.get("building") or 1
            if committed is not None:
                s["bids"] += 1
                n = committed
                # the provable blunder: your own skull inside the first n flips
                if d["own_skull"] and min(n, len(d["mat"])) > d["safe"]:
                    s["doomed"] += 1
                s["bid_sum"] += n
            if d["kind"] == "reply":
                s["replies"] += 1
                s["passes"] += (d["choice"] == "pass")
            if d["kind"] == "raise_to":
                s["rungs"] += 1
                s["went_higher"] += (d["choice"] == "higher")
            if d["kind"] == "which":
                s["places"] += 1
                s["placed_skull"] += (d["choice"] == SKULL)
    return {"seats": {k: dict(v) for k, v in seats.items()},
            "lost": {k: v for k, v in per_game.items()},
            "ends": dict(ends), "games": games, "files": len(files)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = gather(a.roots)
    S = d["seats"]
    order = sorted(S, key=lambda n: -(S[n].get("doomed", 0) / max(S[n].get("bids", 1), 1)))

    print(f"{d['games']} games, {sum(v.get('decisions',0) for v in S.values())} "
          f"real decisions\n")
    print("GUARANTEED-LOSS BIDS -- a bid whose own mat holds a skull inside it.")
    print("Wrong from the player's own information, before anything is turned over.\n")
    print(f"{'seat':12s}{'rate':>9s}{'95% CI':>16s}{'of bids':>10s}")
    print("-" * 48)
    for n in order:
        s = S[n]
        k, t = s.get("doomed", 0), s.get("bids", 0)
        lo, hi = wilson(k, t)
        print(f"{n:12s}{(k/t if t else 0):9.1%}{f'[{lo:.3f}-{hi:.3f}]':>16s}"
              f"{f'{k}/{t}':>10s}")

    print(f"\n{'seat':12s}{'challenges':>12s}{'made good':>11s}{'95% CI':>16s}"
          f"{'discs lost/game':>18s}")
    print("-" * 70)
    for n in order:
        s = S[n]
        c, w = s.get("challenges", 0), s.get("round_wins", 0)
        lo, hi = wilson(w, c)
        m, mlo, mhi = mean_ci([float(x) for x in d["lost"].get(n, [])])
        print(f"{n:12s}{c:12d}{(w/c if c else 0):11.1%}"
              f"{f'[{lo:.2f}-{hi:.2f}]':>16s}{f'{m:.2f} [{mlo:.2f}-{mhi:.2f}]':>18s}")

    print(f"\n{'seat':12s}{'win rate':>10s}{'95% CI':>16s}{'games':>8s}"
          f"{'pass rate':>11s}{'plays skull':>13s}")
    print("-" * 68)
    for n in sorted(S, key=lambda x: -S[x].get("wins", 0) / max(S[x].get("games", 1), 1)):
        s = S[n]
        lo, hi = wilson(s.get("wins", 0), s.get("games", 0))
        pr = s.get("passes", 0) / max(s.get("replies", 1), 1)
        # share of the placements where it actually had a choice: the question
        # is forced once only one kind of disc is left in hand, so this reads as
        # "offered the skull, how often did it put it down"
        sk = s.get("placed_skull", 0) / max(s.get("places", 1), 1)
        print(f"{n:12s}{s.get('wins',0)/max(s.get('games',1),1):10.1%}"
              f"{f'[{lo:.2f}-{hi:.2f}]':>16s}{s.get('games',0):8d}{pr:11.1%}{sk:13.1%}")
    print(f"\nhow games ended: {d['ends']}")
    print("win rate is the weakest column here: four players means a 25% null, and "
          "\nseparating 40% from chance takes about 50 games.")

    if a.out:
        Path(a.out).write_text(json.dumps(d, indent=1))
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
