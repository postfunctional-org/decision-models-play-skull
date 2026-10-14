"""Skull: the rules, four seats, and the five questions a player answers.

Each player holds four discs -- three roses and one skull -- and a mat to stack
them on face down. A round:

  1. placing   Every player puts one disc on their own mat, face down. Then, in
               turn order, each either stacks another or opens the bidding. Once
               a bid is made, no more discs go down.
  2. bidding   The opener names a number. Clockwise, each player raises it or
               passes for good. When one bidder is left they have to deliver.
  3. the flip  They turn over discs one at a time, all of their own mat first,
               then the top disc of any mat they choose. Reach the bid in roses
               and the round is won. Turn over a skull and it is lost, and they
               give up a disc -- their own choice if it was their own skull,
               otherwise blind, drawn by whoever owned it.

Two rounds won takes the game. A player out of discs is out of the game, and if
only one is left they win by default.

Why Skull and not the earlier counting game: a constant answer there was right
56% of the time, and no rule got that under 50% because a two-action game cannot
go there. Here a turn is five different questions and one of them is "whose mat
do I turn over", so there is nothing for a constant to be.

The five questions, each kept as small as the game allows, because three options
offered flat were enough to make most of these models answer by slot position:

    act        stack another disc, or open the bidding          binary
    which      put down a rose, or put down your skull          binary
    open       what to open the bidding at                      a short list
    reply      raise the bid, or pass                           pass + a short list
    whose      which mat to turn over next                      the live mats
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

ROSE, SKULL = "rose", "skull"
HAND = (ROSE, ROSE, ROSE, SKULL)
TO_WIN = 2
BID_CHOICES = 3          # how many rungs of the ladder to offer at once
SHAPES = ("list", "binary")


@dataclass
class Seat:
    name: str
    hand: list[str] = field(default_factory=lambda: list(HAND))
    mat: list[str] = field(default_factory=list)      # bottom to top, face down
    revealed: list[str] = field(default_factory=list)  # turned over, still theirs
    points: int = 0
    out: bool = False

    @property
    def discs(self) -> int:
        """Everything they still own: in hand, on the mat, or face up on the table.

        A turned-over disc is still the owner's and comes back at the end of the
        round. Leaving it out of the count is how a first draft had all four
        players at zero discs by round six.
        """
        return len(self.hand) + len(self.mat) + len(self.revealed)

    def pool(self) -> list[str]:
        return self.hand + self.mat + self.revealed

    def take(self, disc: str) -> None:
        """Remove one disc of that kind from wherever it currently sits."""
        for where in (self.hand, self.mat, self.revealed):
            if disc in where:
                where.remove(disc)
                return
        raise ValueError(f"no {disc} to take from {self.name}")


@dataclass
class Skull:
    names: list[str]
    # how the bidding questions are asked. `list` offers several numbers at once,
    # which is how this started; `binary` walks a ladder of yes/no steps instead,
    # because a five-option list turned out to be answered by slot: gpt-6-luna
    # passed 102 times out of 102 when `pass` happened to be printed first.
    shape: str = "list"
    seats: list[Seat] = field(default_factory=list)
    starter: int = 0
    turn: int = 0
    phase: str = "place"          # place | bid | flip | over
    bid: int = 0
    bidder: int | None = None
    passed: set = field(default_factory=set)
    placed_opening: set = field(default_factory=set)
    intent: str | None = None     # what `act` said to do, until it is carried out
    building: int | None = None   # the bid being walked up, one rung at a time
    flips: list[dict] = field(default_factory=list)
    round_no: int = 0
    log: list[dict] = field(default_factory=list)
    winner: str | None = None
    seed: int = 0
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        self.seats = [Seat(n) for n in self.names]
        self.rng = random.Random(self.seed)
        self._begin_round()

    # -- bookkeeping --------------------------------------------------------
    def active(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if not s.out]

    def live_bidders(self) -> list[int]:
        return [i for i in self.active() if i not in self.passed]

    def on_table(self) -> int:
        return sum(len(self.seats[i].mat) for i in self.active())

    def event(self, kind: str, **kw) -> dict:
        e = {"n": len(self.log), "round": self.round_no, "kind": kind, **kw}
        self.log.append(e)
        return e

    def _next(self, frm: int, pool: list[int]) -> int:
        """The next seat clockwise that is still in `pool`."""
        for step in range(1, len(self.seats) + 1):
            cand = (frm + step) % len(self.seats)
            if cand in pool:
                return cand
        return frm

    def _begin_round(self) -> None:
        self.round_no += 1
        for s in self.seats:
            s.hand = s.hand + s.mat + s.revealed
            s.mat, s.revealed = [], []
        self.phase, self.bid, self.bidder = "place", 0, None
        self.passed, self.placed_opening, self.flips = set(), set(), []
        self.intent, self.building = None, None
        act = self.active()
        if self.starter not in act:
            self.starter = self._next(self.starter, act)
        self.turn = self.starter
        self.event("round_begins", starter=self.seats[self.starter].name,
                   discs={s.name: s.discs for s in self.seats if not s.out})

    # -- what is being asked -----------------------------------------------
    def question(self) -> dict | None:
        """The decision now owed, or None when the game is over."""
        if self.phase == "over":
            return None
        me = self.turn
        seat = self.seats[me]
        if self.phase == "place":
            opening = me not in self.placed_opening
            # a player holding nothing cannot stack, whichever step we are at:
            # the opening placement included, which is reachable after they put
            # their last disc down and the turn comes round again
            if (opening or self.intent == "place") and seat.hand:
                if SKULL in seat.hand and len(seat.hand) > 1:
                    return self._q("which", me)
                return {"kind": "which", "seat": me, "who": seat.name,
                        "options": [seat.hand[0]], "forced": seat.hand[0]}
            if self.intent == "bid" or not seat.hand:
                # nothing left to stack, so bid
                return self._q("raise_to" if self.shape == "binary" else "open", me)
            return self._q("act", me)
        if self.phase == "bid":
            if self.shape == "binary" and self.building is not None:
                return self._q("raise_to", me)
            return self._q("reply", me)
        return self._q("whose", me)

    def _q(self, kind: str, me: int) -> dict:
        q = self._opts(kind, me)
        if len(q["options"]) == 1:
            # one legal answer is not a decision. Marking it forced keeps it out
            # of the models' hands entirely, so an endpoint failing cannot be
            # papered over with "took the first option" and read later as a move
            q["forced"] = q["options"][0]
        return q

    def _opts(self, kind: str, me: int) -> dict:
        q = {"kind": kind, "seat": me, "who": self.seats[me].name}
        if kind == "act":
            q["options"] = ["place", "bid"]
        elif kind == "which":
            q["options"] = [ROSE, SKULL]
        elif kind == "open":
            top = self.on_table()
            q["options"] = [str(n) for n in range(1, min(BID_CHOICES, top) + 1)]
            if top > BID_CHOICES:
                q["options"].append(str(top))      # and the whole table
        elif kind == "raise_to":
            # one rung at a time: commit here, or go one higher. At the top of
            # the table there is nowhere left to go, so it commits itself.
            # a player who ran out of discs is sent straight to the bidding
            # without ever being asked `act`, so the ladder may not be started
            b = self.building or 1
            q["building"] = b
            q["options"] = (["commit"] if b >= self.on_table()
                            else ["commit", "higher"])
        elif kind == "reply" and self.shape == "binary":
            q["options"] = (["pass"] if self.bid >= self.on_table()
                            else ["pass", "raise"])
        elif kind == "reply":
            top = self.on_table()
            rungs = [str(n) for n in range(self.bid + 1,
                                           min(self.bid + BID_CHOICES, top) + 1)]
            if top > self.bid + BID_CHOICES:
                rungs.append(str(top))
            q["options"] = ["pass"] + rungs
        else:
            mine = self.seats[me]
            q["options"] = [self.seats[i].name for i in self.active()
                            if self.seats[i].mat and i != me] \
                if not mine.mat else [mine.name]
        return q

    # -- applying an answer ------------------------------------------------
    def answer(self, choice: str) -> dict:
        q = self.question()
        if q is None:
            raise RuntimeError("the game is over")
        kind, me = q["kind"], q["seat"]
        if "forced" in q:
            choice = q["forced"]
        elif choice not in q["options"]:
            choice = q["options"][0]
        seat = self.seats[me]

        if kind == "which":
            self.intent = None
            seat.hand.remove(choice)
            seat.mat.append(choice)
            e = self.event("places", who=seat.name, hidden=choice,
                           mat=len(seat.mat))
            if me not in self.placed_opening:
                self.placed_opening.add(me)
                if len(self.placed_opening) < len(self.active()):
                    self.turn = self._next(me, self.active())
                    return e
                self.turn = self.starter
                return e
            self.turn = self._next(me, self.active())
            return e

        if kind == "act":
            self.intent = "place" if choice == "place" else "bid"
            if self.intent == "bid" and self.shape == "binary":
                self.building = 1
            return self.event("will_" + self.intent, who=seat.name)

        if kind == "raise_to":
            if choice == "higher":
                self.building = (self.building or 1) + 1
                return self.event("considers", who=seat.name, bid=self.building)
            n, self.building = (self.building or 1), None
            if self.phase == "place":
                self.intent = None
                self.bid, self.bidder = n, me
                self.phase = "bid"
                e = self.event("opens", who=seat.name, bid=self.bid)
                self.turn = self._next(me, self.live_bidders())
                return e
            self.bid, self.bidder = n, me
            e = self.event("raises", who=seat.name, bid=self.bid)
            live = self.live_bidders()
            if len(live) <= 1:
                self.phase, self.turn = "flip", self.bidder
                self.event("challenge", who=self.seats[self.bidder].name,
                           bid=self.bid, table=self.on_table())
            else:
                self.turn = self._next(me, live)
            return e

        if kind == "open":
            self.intent = None
            self.bid, self.bidder = int(choice), me
            self.phase = "bid"
            e = self.event("opens", who=seat.name, bid=self.bid)
            self.turn = self._next(me, self.live_bidders())
            return e

        if kind == "reply":
            if choice == "raise":
                self.building = self.bid + 1
                return self.event("will_raise", who=seat.name)
            if choice == "pass":
                self.passed.add(me)
                e = self.event("passes", who=seat.name)
            else:
                self.bid, self.bidder = int(choice), me
                e = self.event("raises", who=seat.name, bid=self.bid)
            live = self.live_bidders()
            if len(live) <= 1:
                self.phase, self.turn = "flip", self.bidder
                self.event("challenge", who=self.seats[self.bidder].name,
                           bid=self.bid, table=self.on_table())
            else:
                self.turn = self._next(me, live)
            return e

        return self._flip(me, choice)

    def _flip(self, me: int, whose: str) -> dict:
        owner = self.names.index(whose)
        disc = self.seats[owner].mat.pop()
        self.seats[owner].revealed.append(disc)
        self.flips.append({"owner": whose, "disc": disc})
        e = self.event("flips", who=self.seats[me].name, owner=whose, disc=disc,
                       count=len(self.flips), bid=self.bid)
        if disc == SKULL:
            self._fails(me, owner)
        elif len(self.flips) >= self.bid:
            self._succeeds(me)
        return e

    def _succeeds(self, me: int) -> None:
        seat = self.seats[me]
        seat.points += 1
        self.event("wins_round", who=seat.name, points=seat.points)
        self.starter = me
        if seat.points >= TO_WIN:
            self.winner, self.phase = seat.name, "over"
            self.event("wins_game", who=seat.name, how=f"{TO_WIN} rounds")
            return
        self._begin_round()

    def _fails(self, me: int, owner: int) -> None:
        seat = self.seats[me]
        own = owner == me
        # their own skull is theirs to choose from; anyone else's is drawn blind
        pool = seat.pool()
        lost = (SKULL if own and SKULL in pool else
                (ROSE if own and pool else self.rng.choice(pool))) if pool else None
        if lost:
            seat.take(lost)
        self.event("fails", who=seat.name, skull_of=self.names[owner],
                   lost=lost, chosen_by=(seat.name if own else self.names[owner]),
                   left=seat.discs)
        if seat.discs == 0:
            seat.out = True
            self.event("eliminated", who=seat.name)
        self.starter = owner if not self.seats[owner].out else \
            self._next(owner, self.active() or [owner])
        act = self.active()
        if len(act) <= 1:
            self.winner = self.seats[act[0]].name if act else None
            self.phase = "over"
            self.event("wins_game", who=self.winner, how="last one standing")
            return
        self._begin_round()
