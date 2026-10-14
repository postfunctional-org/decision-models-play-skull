#!/usr/bin/env python3
"""Play many games unattended, and bank each transcript.

Only seats that answer in-process can be in a batch: the four models and the
scripted bars. A seat played by hand cannot, which is the whole reason this file
is separate from skull/play.py. The first game was played that way, with a
fresh Claude Code subagent answering for Haiku every turn: about 35 round trips
a game, which is fine for one game and not for a hundred.

Seats rotate by one each game so no model keeps a seat advantage: with four
players, turn order matters and the first game of the first run had the starter
winning on a bid nobody contested.

    python3 -m skull.batch --seats Jev OpenJev LUNA Haiku --games 100 --out games/list
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path

from skull.ask import observation
from skull.game import SHAPES, Skull
from skull.play import agent

MAX_STEPS = 4000


def one(seats: list[str], seed: int, agents: dict, shape: str = "list") -> dict:
    g = Skull(names=list(seats), seed=seed, shape=shape)
    answers, invalid, steps = [], [], 0
    while steps < MAX_STEPS:
        q = g.question()
        if q is None:
            break
        if "forced" in q:
            g.answer(q["forced"]); answers.append(q["forced"]); steps += 1
            continue
        obs = observation(g, q["seat"], q)
        choice = None
        for attempt in range(4):
            try:
                choice, _ = agents[q["who"]].pick(g, q["seat"], obs)
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        if choice is None:
            raise RuntimeError(f"{q['who']} unreachable on a {q['kind']} decision")
        if choice not in q["options"]:
            invalid.append({"n": len(answers), "who": q["who"], "kind": q["kind"],
                            "answered": choice, "options": q["options"]})
            choice = q["options"][0]
        g.answer(choice); answers.append(choice); steps += 1
    return {"seed": seed, "names": g.names, "shape": shape,
            "answers": answers, "log": g.log,
            "winner": g.winner, "rounds": g.round_no, "invalid": invalid,
            "points": {s.name: s.points for s in g.seats},
            "discs": {s.name: s.discs for s in g.seats}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seats", nargs="+", required=True)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--first-seed", type=int, default=1000)
    ap.add_argument("--shape", default="list", choices=SHAPES,
                    help="how the bidding questions are asked")
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    agents = {n: agent(n) for n in set(a.seats)}

    def task(i: int):
        # rotate the seating each game so turn order is not a model's advantage
        seats = a.seats[i % len(a.seats):] + a.seats[:i % len(a.seats)]
        f = out / f"g{i:04d}.json"
        if f.exists() and f.stat().st_size > 0:
            return i, "skip"
        try:
            r = one(seats, a.first_seed + i, agents, a.shape)
        except Exception as e:
            return i, f"FAIL {type(e).__name__}: {e}"
        f.write_text(json.dumps(r))
        return i, r["winner"]

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for i, res in ex.map(task, range(a.games)):
            done += 1
            print(f"  [{done:4d}/{a.games}] g{i:04d} -> {res}", flush=True)
    print(f"\nwrote {a.games} transcripts to {out}")


if __name__ == "__main__":
    main()
