#!/usr/bin/env python3
"""Time real Skull questions: the same positions put to each model, back to back.

Positions come from recorded games, replayed; each one is asked of every model
in turn, so network weather hits them alike. The video's speed comparison
comes from this.

    python3 -m skull.latency Jev,LUNA,Haiku 30 results/latency.json

Needs the keys skull/play.py needs for each model named.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time
from pathlib import Path

from skull.ask import observation
from skull.game import Skull
from skull.play import agent

ROOT = Path(__file__).resolve().parent.parent


def positions(n_games: int = 12) -> list[dict]:
    out = []
    for f in sorted((ROOT / "games/list").glob("g*.json"))[:n_games]:
        t = json.loads(f.read_text())
        g = Skull(names=list(t["names"]), seed=t["seed"], shape=t.get("shape", "list"))
        for ch in t["answers"]:
            q = g.question()
            if q is None:
                break
            if "forced" not in q:
                out.append(observation(g, q["seat"], q))
            g.answer(ch)
    random.Random(7).shuffle(out)
    return out


def main() -> None:
    models, n, dest = sys.argv[1].split(","), int(sys.argv[2]), Path(sys.argv[3])
    agents = {m: agent(m) for m in models}
    raw = {m: [] for m in models}
    for i, obs in enumerate(positions()[:n]):
        for m in models:
            t0 = time.time()
            agents[m].pick(None, None, obs)
            raw[m].append(round(1000 * (time.time() - t0), 1))
        print(i, {m: raw[m][-1] for m in models}, flush=True)
    summary = {m: {"n": len(v), "median_ms": statistics.median(v),
                   "p10": sorted(v)[len(v) // 10], "p90": sorted(v)[len(v) * 9 // 10]}
               for m, v in raw.items()}
    dest.write_text(json.dumps({"raw": raw, "summary": summary,
                                "when": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
