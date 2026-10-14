# Notes from the first game

Written while the first full game (games/first) was still being played, so the
numbers here come from one game and should be read as things to check, not as
results. Haiku answered that game through a fresh Claude Code subagent every
turn, which is why its reasoning is quoted below; in the batches it answers in
one word and gives none.

## The prompt has to be read, not just written

Two descriptions in `ask.py` told a player something untrue about its own
position, and both were found by reading the text a model was about to be
handed rather than by any test.

- The mat was printed as a count — "1 rose and 1 skull" — when a stack is
  flipped from the top and which disc sits where is precisely what its owner
  knows and nobody else does.
- Every bid was described as "starting with all N of your own", N being the
  whole stack. You turn over your own mat first but **only as far as the bid**,
  so a player with a skull at the bottom of a three-stack can safely bid two.
  HAIKU-4 was sitting on exactly that stack — skull, rose, rose — reading that
  a bid of two would turn over three discs including its own skull.

The fix changed its play immediately. Asked again with the corrected wording it
bid 2 and said in as many words that 3 would hit its own skull. That is the
same effect a wording test on an earlier two-action game measured (the wording
moved between 27% and 77% of these models' picks there), showing up as a
correctness bug rather than a bias.

## A model can be told a thing plainly and not use it

Round 3, HAIKU-4's mat held one disc: its own skull. The state said
`On your own mat, face down, bottom to top: skull.` Every bid option said
`the first 1 would come off your own stack`. It opened the bidding anyway, and
its stated reasoning put bid-1 at "~60% success rate (3 roses out of 5 discs)"
— averaging over the whole table while the only disc it would actually turn
over was named, in its own prompt, two lines above.

This is the earlier game's finding again: four of ten models there
answered with a constant and the rest were moved more by wording and slot
position than by the state. Skull makes the failure legible, because here it
has a consequence you can watch.

## Single-option questions are not decisions

43% of the questions this engine generates have exactly one legal answer
(3888 of 8932 across 60 games). They now resolve without asking anyone. Worth
doing for cost alone, but the real reason is that a model call that cannot fail
to be "right" is a place where an endpoint failure gets recorded as a move —
which is how a LUNA HTTP error nearly entered the log as a decision.
