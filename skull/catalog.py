#!/usr/bin/env python3
"""The recorded games the viewer offers in its picker, written to games/index.json.

Run it after adding games. tests/test_games.py fails while the list is stale.

    python3 -m skull.catalog
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = [("first", "The first game, Haiku through Claude Code"),
          ("list", "Four models"),
          ("binary", "Four models, bidding asked as yes or no"),
          ("vs_house", "Three models and house"),
          ("vs_random", "Three models and random"),
          ("bars", "Scripted players only")]


def build() -> list[dict]:
    out = []
    for folder, title in GROUPS:
        games = []
        for f in sorted((ROOT / "games" / folder).glob("*.json")):
            t = json.loads(f.read_text())
            games.append({"run": f"games/{folder}/{f.name}",
                          "name": folder if f.stem == "transcript" else f.stem,
                          "winner": t.get("winner"), "rounds": t.get("rounds")})
        out.append({"title": title, "games": games})
    return out


def main() -> None:
    path = ROOT / "games" / "index.json"
    groups = build()
    path.write_text(json.dumps(groups, indent=1) + "\n")
    print(f"{sum(len(g['games']) for g in groups)} games listed in {path}")


if __name__ == "__main__":
    main()
