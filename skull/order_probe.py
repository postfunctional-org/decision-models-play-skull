#!/usr/bin/env python3
"""One position, both option orders, at two list lengths.

The cheapest test of whether an answer is an answer or a slot -- and the list
length is part of it, because a model can be steady on a binary question and
fall apart on the five-option one the game actually asks.

The position is chosen so there is nothing to think about: the player's own mat
is two roses, so bidding 2 wins the round outright with no other mat touched.
Any answer other than `2` is wrong, whatever order it was shown in.

    python3 -m skull.order_probe --agent LUNA --repeat 30 --out results/luna_order.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skull.play import agent

STATE = ("Round 3. You are LUNA-6. Rounds won: 0.\n"
         "In your hand: 2 roses.\n"
         "On your own mat, face down, bottom to top: rose, rose.\n"
         "Discs face down on the table in total: 6.\n"
         "The bid stands at 1, made by JEV-1.")

OPTS = {
    "pass": "Take no further part in the bidding this round. You cannot bid "
            "again until the next round.",
    "2": "Bid 2. If you end up running it you must turn over 2 discs without "
         "hitting a skull. You turn over your own mat first, from the top down, "
         "so both would come off your own stack. That reaches the bid, so you "
         "would not touch anyone else's mat.",
    "3": "Bid 3. The first 2 would come off your own stack, and the remaining 1 "
         "from the top of a mat you choose.",
    "4": "Bid 4. The first 2 would come off your own stack, and the remaining 2 "
         "from the top of mats you choose.",
    "6": "Bid 6. The first 2 would come off your own stack, and the remaining 4 "
         "from the top of mats you choose.",
}

SHAPES = [("two options", [["pass", "2"], ["2", "pass"]]),
          ("five options, as the game asks them",
           [["pass", "2", "3", "4", "6"], ["6", "4", "3", "2", "pass"]])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--repeat", type=int, default=1,
                    help="ask each order this many times. One call cannot tell a "
                         "slot preference from a coin; a run of them can.")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    tally: dict[str, dict] = {}
    asked = agent(a.agent)
    print(f"{a.agent}: own mat is two roses, so `2` is a free round win.")
    for label, orders in SHAPES:
        print(f"  -- {label}")
        for order in orders:
          where = "first" if order[0] == "pass" else "last"
          key = f"{label}|pass {where}"
          tally[key] = {"shape": label, "pass_position": where,
                        "n": 0, "picks": {}}
          for _ in range(a.repeat):
            obs = {"state": STATE,
                   "instructions": "Pick the option that gives you the best "
                                   "chance of winning the game.",
                   "candidates": [{"id": k, "desc": OPTS[k]} for k in order],
                   "pid": "probe", "env": "probe"}
            try:
                pick, info = asked.pick(None, 0, obs)
            except Exception as e:
                print(f"     {type(e).__name__}: {e}")
                continue
            t = tally[key]
            t["n"] += 1
            t["picks"][pick] = t["picks"].get(pick, 0) + 1
          t = tally[key]
          if t["n"]:
              right = t["picks"].get("2", 0)
              stepped = t["picks"].get("pass", 0)
              print(f"     pass {where:5s} -> free win {right}/{t['n']}, "
                    f"stepped back {stepped}/{t['n']}   "
                    + ", ".join(f"{k}={v}" for k, v in sorted(t["picks"].items())))
    print()
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(
            {"agent": a.agent, "repeat": a.repeat, "tally": tally}, indent=1))
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
