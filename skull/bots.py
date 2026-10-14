"""Scripted players, for the floor and for the bulk runs.

Two of them, and both exist to make the model numbers mean something:

    random   picks uniformly from whatever it is offered. The floor. If a model
             cannot beat this, the game is measuring nothing about it.
    house    a competent, entirely mechanical player. It bids no deeper than its
             own roses go, which is the error the stats tool counts. It can still
             be forced into one: an empty hand with its skull on top has no safe
             bid to open with. In practice it stacks one rose and opens, so in
             the recorded games its skull was never down when it claimed.

`house` is deliberately simple and deliberately honest about its own stack. It
knows what it placed, because every player does, and it bids only as deep as its
own roses go. Everything beyond that it leaves to whoever wants the risk.
"""

from __future__ import annotations

import hashlib

from skull.game import ROSE, SKULL


def _h(salt, key: str, n: int) -> int:
    return int(hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()[:8], 16) % n


class Random:
    """Uniform over the options. The floor."""
    kind = "bar"

    def __init__(self, name="random", salt=0):
        self.name, self.salt = name, salt

    def pick(self, g, pid, obs):
        ids = [c["id"] for c in obs["candidates"]]
        return ids[_h(self.salt, obs["pid"], len(ids))], {}


class House:
    """Mechanical but sane. Never bids past its own skull."""
    kind = "bar"

    def __init__(self, name="house", salt=0):
        self.name, self.salt = name, salt

    @staticmethod
    def cap(seat, table: int) -> int:
        """The deepest bid that is not a guaranteed loss, plus a little nerve.

        Flipping goes top-down through your own mat first, so a bid deeper than
        your own roses turns your own skull over. If your mat holds no skull at
        all there is nothing of yours to hit, and you can reach into other mats
        -- each of which is about three-quarters roses early on, so two extra is
        a real bet rather than a wild one. A first version stopped dead at its
        own roses, never ran a challenge, and lost to the random bar.
        """
        s = House.safe(seat)
        return s if SKULL in seat.mat else min(table, s + 2)

    @staticmethod
    def safe(seat) -> int:
        """How many discs it can turn over from its own mat before its skull.

        The mat is bottom-to-top and flipping goes top-down, so this counts
        roses from the end of the list backwards.
        """
        n = 0
        for d in reversed(seat.mat):
            if d == SKULL:
                break
            n += 1
        return n

    def pick(self, g, pid, obs):
        seat = g.seats[pid]
        ids = [c["id"] for c in obs["candidates"]]
        kind = obs["pid"].rsplit(":", 1)[1] if ":" in obs["pid"] else ""
        q = g.question() or {}
        kind = q.get("kind", kind)
        safe = self.safe(seat)

        if kind == "which":
            # a rose first; the skull once there is a rose over it to hide under,
            # and never as the top disc, which would only trap itself
            want = ROSE if (not seat.mat or SKULL not in seat.hand) else (
                SKULL if len(seat.mat) >= 1 and len(seat.hand) > 1 else ROSE)
            return (want if want in ids else ids[0]), {}

        cap = self.cap(seat, g.on_table())

        if kind == "act":
            # stack while it is cheap; open once it can back a bid worth making
            return ("bid" if (safe >= 1 or not seat.hand) else "place"), {}

        if kind == "open":
            best = max((int(x) for x in ids if x.isdigit() and int(x) <= max(cap, 1)),
                       default=None)
            return (str(best) if best else min(
                (x for x in ids if x.isdigit()), key=int)), {}

        if kind == "reply":
            up = [int(x) for x in ids if x.isdigit() and int(x) <= cap]
            return (str(max(up)) if up else "pass"), {}

        # whose: its own mat while it has one, else the biggest stack going
        if seat.name in ids:
            return seat.name, {}
        best = max(ids, key=lambda n: len(g.seats[g.names.index(n)].mat))
        return best, {}


def build(spec: str):
    if spec.startswith("random"):
        return Random(spec, int(spec.partition(":")[2] or 0))
    if spec.startswith("house"):
        return House(spec, int(spec.partition(":")[2] or 0))
    return None
