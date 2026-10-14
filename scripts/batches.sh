#!/usr/bin/env bash
# The batches behind the recorded games, with the seeds they used.
#
# Needs the keys skull/play.py asks for (JEV_API_KEY, OPENAI_API_KEY,
# ANTHROPIC_API_KEY) and OpenJev served at OPENJEV_BASE_URL. Model answers are
# not deterministic, so a rerun plays new games rather than these, and it
# writes them under games/new/ so the recorded ones are never touched. A batch
# skips any game already on disk, so an interrupted run picks up where it was.
set -eu
cd "$(dirname "$0")/.."
OUT=${OUT:-games/new}

python3 -m skull.batch --seats Jev OpenJev LUNA Haiku --games 100 --jobs 4 \
  --first-seed 20000 --out "$OUT/list"
python3 -m skull.batch --seats Jev OpenJev LUNA Haiku --games 100 --jobs 4 \
  --first-seed 20000 --shape binary --out "$OUT/binary"
python3 -m skull.batch --seats Jev OpenJev LUNA house --games 60 --jobs 4 \
  --first-seed 1000 --out "$OUT/vs_house"
python3 -m skull.batch --seats Jev OpenJev LUNA random --games 60 --jobs 4 \
  --first-seed 5000 --out "$OUT/vs_random"
python3 -m skull.batch --seats house random house:1 random:1 --games 200 --jobs 8 \
  --first-seed 9000 --out "$OUT/bars"
