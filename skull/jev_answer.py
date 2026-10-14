#!/usr/bin/env python3
"""Ask Jev, live, one recorded position, and keep its probabilities.

The video's "decision model" diagram shows a real answer, not a made-up one:
g0065, Jev replying when the claim stood at 6 -- the step where it said seven.
Asked again on 2026-10-13 it still picked seven, at 0.49, which is why that
position and not the claim of nine (where it now picks "pass") is the one shown.

    python3 -m skull.jev_answer games/list/g0065.json 6 results/jev_seven.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from skull.ask import observation
from skull.game import Skull
from skull.play import agent


def main() -> None:
    run, bid, dest = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    t = json.loads(run.read_text())
    g = Skull(names=list(t["names"]), seed=t["seed"], shape=t.get("shape", "list"))
    a = agent("Jev")
    for ch in t["answers"]:
        q = g.question()
        if q is None:
            break
        if "forced" not in q and q["who"] == "Jev" and q["kind"] == "reply" and g.bid == bid:
            obs = observation(g, q["seat"], q)
            pick, meta = a.pick(None, None, obs)
            dest.write_text(json.dumps({"file": str(run), "obs": obs, "options": q["options"],
                                        "game": ch, "now": pick, "meta": meta}, indent=1))
            print(f"in the game: {ch}   now: {pick}   {meta['probs']}")
            return
        g.answer(ch)
    raise SystemExit(f"no Jev reply at a bid of {bid} in {run}")


if __name__ == "__main__":
    main()
