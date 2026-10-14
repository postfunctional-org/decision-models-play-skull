"""What a player is shown, and the five option lists they choose from.

A player knows their own discs -- the ones in their hand and the ones they put on
their own mat face down, because they put them there. They do not know what is
under anyone else's. That asymmetry is the game, so the state below is built
per seat and says only what that seat can see.

Option descriptions are written in the flat register, stating what happens and
not how it feels. On the counting game the wording moved between 27% and 77% of
these models' picks with the facts untouched, and the two wordings that differed
only in tone moved them most, so there is no upside in colour here.
"""

from __future__ import annotations

import hashlib

from skull.game import ROSE, SKULL, TO_WIN
from skull.table import seat as look

INSTRUCTIONS = ("You are playing Skull. Pick the option that gives you the best "
                "chance of winning the game.")


def state(g, me: int) -> str:
    seat = g.seats[me]
    lines = [
        f"Round {g.round_no}. First to {TO_WIN} rounds won takes the game.",
        "",
        f"You are {look(seat.name)['label']}. Rounds won: {seat.points}.",
        f"In your hand: {fmt(seat.hand)}.",
        # in order, not as a count: the stack is flipped from the top, so which
        # disc is where is part of what this player knows and the others do not
        f"On your own mat, face down, bottom to top: "
        f"{', '.join(seat.mat) if seat.mat else 'nothing'}.",
        "",
        "The others:",
    ]
    for i, s in enumerate(g.seats):
        if i == me:
            continue
        if s.out:
            lines.append(f"  {look(s.name)['label']}: out of the game.")
            continue
        lines.append(
            f"  {look(s.name)['label']}: {len(s.mat)} disc(s) face down on their "
            f"mat, {s.discs} disc(s) still theirs, {s.points} round(s) won.")
    lines += ["", f"Discs face down on the table in total: {g.on_table()}."]
    if g.bidder is not None:
        lines.append(f"The bid stands at {g.bid}, made by "
                     f"{look(g.seats[g.bidder].name)['label']}.")
    if g.passed:
        lines.append("Passed this round: "
                     + ", ".join(look(g.seats[i].name)['label'] for i in g.passed))
    if g.flips:
        shown = ", ".join(f"{look(f['owner'])['label']}'s {f['disc']}"
                          for f in g.flips)
        lines.append(f"Turned over so far: {shown}.")
    return "\n".join(lines)


def fmt(discs: list[str]) -> str:
    r = sum(1 for d in discs if d == ROSE)
    s = sum(1 for d in discs if d == SKULL)
    bits = []
    if r:
        bits.append(f"{r} rose" + ("s" if r > 1 else ""))
    if s:
        bits.append("1 skull")
    return " and ".join(bits)


def describe(g, me: int, q: dict) -> list[dict]:
    seat = g.seats[me]
    kind = q["kind"]
    build = q.get("building", 1)
    own = len(seat.mat)
    out = []
    for opt in q["options"]:
        if kind == "act":
            d = ("Put another disc from your hand onto your own mat, face down. "
                 "The bidding has not started, so it stays open."
                 if opt == "place" else
                 "Stop placing and open the bidding. You will name a number of "
                 "discs, and if nobody outbids you, you have to turn over that "
                 "many without turning over a skull.")
        elif kind == "which":
            d = ("Place a rose. If it is turned over it counts towards whoever's "
                 "bid is being run." if opt == ROSE else
                 "Place your skull. Whoever turns it over fails their bid and "
                 f"loses a disc, and you choose which one at random. You hold "
                 f"{'it' if SKULL in seat.hand else 'no skull'}.")
        elif kind == "raise_to":
            if opt == "commit":
                mine = min(build, own)
                d = (f"Settle on {build}. If nobody outbids you, you must turn "
                     f"over {build} disc(s) without hitting a skull. You turn "
                     f"over your own mat first, from the top down, so the first "
                     f"{mine} would come off your own stack"
                     + (f", and the remaining {build - mine} from the top of "
                        "mats you choose." if build > own else
                        ". That reaches it, so you would not touch anyone "
                        "else's mat.")
                     + f" {g.on_table()} discs are face down in total.")
            else:
                d = (f"Do not settle yet. Consider {build + 1} instead, one "
                     f"higher. You are not committed to anything until you "
                     f"settle.")
        elif kind == "reply" and opt == "raise":
            d = (f"Outbid them. The bid stands at {g.bid}, so you would start "
                 f"from {g.bid + 1} and settle on a number from there, one step "
                 "at a time.")
        elif kind in ("open", "reply") and opt == "pass":
            d = ("Take no further part in the bidding this round. You cannot bid "
                 "again until the next round.")
        elif kind in ("open", "reply"):
            n = int(opt)
            own = len(seat.mat)
            mine = min(n, own)
            # you flip your own first, from the top, but only as far as the bid:
            # saying "all N of your own" is wrong and badly so, because a player
            # with a skull at the bottom of a deep stack can still bid under it
            d = (f"Bid {n}. If you end up running it you must turn over {n} disc(s) "
                 f"without hitting a skull. You turn over your own mat first, from "
                 f"the top down, so the first {mine} would come off your own stack"
                 + (f", and the remaining {n - mine} from the top of mats you choose."
                    if n > own else ". That reaches the bid, so you would not touch "
                    "anyone else's mat.")
                 + f" {g.on_table()} discs are face down in total.")
        else:
            s = g.seats[g.names.index(opt)]
            mine = opt == seat.name
            d = (f"Turn over the top disc of your own mat. You have "
                 f"{len(s.mat)} left there and must clear it before any other."
                 if mine else
                 f"Turn over the top disc of {look(opt)['label']}'s mat. They "
                 f"have {len(s.mat)} disc(s) face down and {s.discs} in all.")
        out.append({"id": opt, "desc": d})
    # seeded per question, for the same reason the counting game shuffles its two:
    # a fixed order measures the harness, and these models pick by slot
    key = f"{g.seed}:{len(g.log)}:{me}:{kind}"
    if int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 2:
        out.reverse()
    return out


def observation(g, me: int, q: dict) -> dict:
    return {"state": state(g, me), "candidates": describe(g, me, q),
            "instructions": INSTRUCTIONS,
            "pid": f"{g.seed}:{len(g.log)}:{q['kind']}",
            "env": f"skull:{g.seed}"}
