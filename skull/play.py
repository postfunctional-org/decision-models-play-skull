#!/usr/bin/env python3
"""Play one game of Skull, one answer at a time.

A seat is a model from skull/table.py, which answers over HTTP, a scripted bar
(`random`, `house`), or a seat played by hand. When it is a hand-played seat's
turn, the driver writes the question to `pending.json`, prints it in full and
stops. Answer it and run the driver again:

    python3 -m skull.play --out games/mine                        # the four models
    python3 -m skull.play --out games/mine --by-hand Haiku        # sit in for Haiku
    python3 -m skull.play --out games/mine --answer rose          # ...and answer
    python3 -m skull.play --out games/solo --seats you house random house:1 --by-hand you

The state is not serialised. The engine is deterministic given a seed and the
list of answers so far, so the transcript IS the save file -- replaying it costs
nothing and cannot drift from what actually happened. Interrupt a game and run
the same command again; it picks up where it stopped.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from skull.ask import observation
from skull.bots import build as build_bar
from skull.game import SHAPES, Skull
from skull.model import from_env
from skull.table import ORDER, SEATS, say, seat as look


def configure(name: str) -> None:
    """Put a seat's endpoint into the environment the model client reads.

    Anything already set wins, so a seat can be pointed somewhere else without
    touching skull/table.py. The key falls back to the provider's usual name.
    """
    api = SEATS[name]["api"]
    up = api["env"]
    os.environ.setdefault(f"{up}_BASE_URL", api["base"])
    os.environ.setdefault(f"{up}_MODEL", api["model"])
    os.environ.setdefault(f"{up}_API", api["shape"])
    if api.get("key") and os.environ.get(api["key"]):
        os.environ.setdefault(f"{up}_API_KEY", os.environ[api["key"]])


def agent(name: str):
    """Whoever answers for this seat: a scripted bar, or a model over HTTP."""
    bar = build_bar(name)
    if bar:
        return bar
    if name not in SEATS:
        raise SystemExit(f"{name} is neither a model in skull/table.py nor a "
                         f"scripted bar (random, house). To play it yourself, "
                         f"add --by-hand {name}")
    configure(name)
    up = SEATS[name]["api"]["env"]
    local = any(h in os.environ[f"{up}_BASE_URL"] for h in ("127.0.0.1", "localhost"))
    if not local and not os.environ.get(f"{up}_API_KEY"):
        also = SEATS[name]["api"].get("key")
        raise SystemExit(f"{name} needs {up}_API_KEY" + (f" (or {also})" if also else "")
                         + f" in the environment. To play it yourself instead, "
                         f"add --by-hand {name}")
    a = from_env(name)
    a.name = name
    return a


def save(path: Path, banked: dict, answers: list[str], g: Skull) -> None:
    """Bank the transcript. The log goes in on every save, not only at the end,
    so the viewer can follow a game that is still being played."""
    path.write_text(json.dumps(
        {**banked, "answers": answers, "log": g.log, "winner": g.winner,
         "rounds": g.round_no,
         "points": {s.name: s.points for s in g.seats},
         "discs": {s.name: s.discs for s in g.seats}}, indent=1))


def rebuild(t: dict, answers: list[str]) -> Skull:
    g = Skull(names=list(t["names"]), seed=t["seed"], shape=t.get("shape", "list"))
    for a in answers:
        if g.question() is None:
            break
        g.answer(a)
    return g


def show(out: Path, q: dict, obs: dict) -> None:
    """The question exactly as a model would read it, and how to answer it."""
    print(f"\n== {look(q['who'])['label']} to answer ({q['kind']})")
    print("-" * 64)
    print(obs["instructions"])
    print()
    print(obs["state"])
    print()
    print("Your options:")
    for c in obs["candidates"]:
        print(f"* {c['id']} -- {c['desc']}")
    print("-" * 64)
    print(f"answer with:  python3 -m skull.play --out {out} --answer <option>")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True,
                    help="the game's folder; the same command again carries on")
    ap.add_argument("--seats", nargs="+", default=list(ORDER), metavar="SEAT",
                    help="in turn order: models from skull/table.py, random, "
                         "house, or any name played --by-hand")
    ap.add_argument("--by-hand", nargs="+", default=[], metavar="SEAT",
                    help="seats answered with --answer, by a person or an agent")
    ap.add_argument("--answer", help="the answer to the question the game stopped on")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--shape", default="list", choices=SHAPES,
                    help="how the bidding questions are asked")
    ap.add_argument("--max-steps", type=int, default=400)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tpath, ppath = out / "transcript.json", out / "pending.json"

    # a game already under way keeps the seats, seed and shape it started with
    banked = json.loads(tpath.read_text()) if tpath.exists() else \
        {"seed": args.seed, "names": list(args.seats), "shape": args.shape,
         "by_hand": list(args.by_hand), "answers": []}
    answers = banked["answers"]
    by_hand = set(banked.get("by_hand", []))
    agents = {n: agent(n) for n in set(banked["names"]) - by_hand}

    g = rebuild(banked, answers)
    if args.answer is not None:
        q = g.question()
        if q is None:
            raise SystemExit("the game is already over")
        if q["who"] not in by_hand:
            raise SystemExit(f"it is {q['who']}'s turn, and {q['who']} is not "
                             f"played by hand")
        if args.answer not in q["options"]:
            show(out, q, observation(g, q["seat"], q))
            raise SystemExit(f"\n{args.answer!r} is not one of the options: "
                             f"{', '.join(q['options'])}")
        report(g.answer(args.answer))
        answers.append(args.answer)

    steps = 0
    while steps < args.max_steps:
        q = g.question()
        if q is None:
            break
        if "forced" in q:
            e = g.answer(q["forced"])
            answers.append(q["forced"])
            report(e)
            continue
        who = q["who"]
        obs = observation(g, q["seat"], q)
        if who in by_hand:
            ppath.write_text(json.dumps(
                {"who": who, "kind": q["kind"], "options": [c["id"] for c in
                                                            obs["candidates"]],
                 "state": obs["state"], "instructions": obs["instructions"],
                 "candidates": obs["candidates"]}, indent=1))
            save(tpath, banked, answers, g)
            show(out, q, obs)
            return
        choice, failed = None, None
        for attempt in range(4):
            try:
                choice, _ = agents[who].pick(g, q["seat"], obs)
                break
            except Exception as ex:
                failed = f"{type(ex).__name__}: {ex}"
                print(f"  .. {who} call failed ({type(ex).__name__}), "
                      f"retry {attempt + 1}/3")
                time.sleep(5 * (attempt + 1))
        if choice is None:
            # never quietly substitute a default for a real decision: stop, say
            # so, and let it be resumed once the endpoint is back
            print(f"\n!! {who} could not be reached for a {q['kind']} decision "
                  f"with {len(q['options'])} options ({failed}).")
            print("   Stopping rather than answering for it. Fix the endpoint "
                  "and run again; the transcript resumes where it left off.")
            save(tpath, banked, answers, g)
            return
        if choice not in q["options"]:
            print(f"  !! {who} answered {choice!r}, not in {q['options']}; "
                  f"recording the first option and flagging it")
            banked.setdefault("invalid", []).append(
                {"n": len(answers), "who": who, "kind": q["kind"],
                 "answered": choice, "options": q["options"]})
            choice = q["options"][0]
        e = g.answer(choice)
        answers.append(choice)
        report(e)
        steps += 1

    if ppath.exists():
        ppath.unlink()
    save(tpath, banked, answers, g)
    if g.winner:
        print(f"\n=== {look(g.winner)['label']} wins after {g.round_no} rounds")
    else:
        print(f"\n=== stopped after {args.max_steps} steps, no winner yet")
    print(f"wrote {tpath}")


def report(e: dict) -> None:
    k = e["kind"]
    if k == "places":
        print(f"  r{e['round']} {look(e['who'])['label']:8s} places a disc "
              f"({e['mat']} on the mat)")
        return
    if k in ("will_place", "will_bid"):
        return
    line = say(e)
    # `hidden` and `lost` are what nobody else at the table gets to see
    bits = {x: e[x] for x in e
            if x not in ("n", "round", "kind", "who", "hidden", "lost")}
    print(f"  r{e['round']} {look(e.get('who') or '?')['label']:8s} "
          f"{k:13s} {bits}" + (f'   "{line}"' if line else ""))


if __name__ == "__main__":
    main()
