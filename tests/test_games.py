"""Checks on the recorded games and the tools around them. No network, no keys.

    python3 -m unittest
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from skull import catalog
from skull.game import Skull
from skull.stats import gather

ROOT = Path(__file__).resolve().parent.parent
GAMES = sorted((ROOT / "games").glob("*/*.json"))


class Replay(unittest.TestCase):
    def test_every_game_replays_to_its_own_log(self):
        """The transcript is the save file, so a rule change shows up here."""
        self.assertEqual(len(GAMES), 518)
        for f in GAMES:
            t = json.loads(f.read_text())
            g = Skull(names=list(t["names"]), seed=t["seed"],
                      shape=t.get("shape", "list"))
            for a in t["answers"]:
                if g.question() is None:
                    break
                g.answer(a)
            with self.subTest(game=str(f.relative_to(ROOT))):
                self.assertEqual(g.log, t["log"])
                self.assertEqual(g.winner, t["winner"])


class Results(unittest.TestCase):
    def test_published_stats_come_from_the_games(self):
        """results/stats_*.json are what skull/stats.py says about games/."""
        arms = {"list": ["list"], "binary": ["binary"],
                "vs_bars": ["vs_house", "vs_random"], "bars": ["bars"]}
        for arm, folders in arms.items():
            want = json.loads((ROOT / "results" / f"stats_{arm}.json").read_text())
            got = gather([str(ROOT / "games" / f) for f in folders])
            with self.subTest(arm=arm):
                self.assertEqual(json.loads(json.dumps(got["seats"])), want["seats"])


class Lists(unittest.TestCase):
    def test_viewer_game_list_is_current(self):
        listed = json.loads((ROOT / "games" / "index.json").read_text())
        self.assertEqual(listed, catalog.build(), "run python3 -m skull.catalog")

    def test_voice_list_is_current(self):
        clips = ROOT / "assets" / "voices"
        listed = json.loads((clips / "index.json").read_text())
        self.assertEqual(listed, sorted(p.name for p in clips.glob("*.mp3")),
                         "run python3 -m skull.speak --index-only")


class ByHand(unittest.TestCase):
    def test_a_person_can_sit_in(self):
        """Three scripted players and one seat played by hand, two answers in."""
        with tempfile.TemporaryDirectory() as d:
            def play(*extra):
                return subprocess.run(
                    [sys.executable, "-m", "skull.play", "--out", d, *extra],
                    cwd=ROOT, capture_output=True, text=True, check=True).stdout
            first = play("--seats", "you", "house", "random", "house:1",
                         "--by-hand", "you")
            self.assertIn("YOU to answer (which)", first)
            for _ in range(2):
                pending = json.loads((Path(d) / "pending.json").read_text())
                play("--answer", pending["options"][0])
            t = json.loads((Path(d) / "transcript.json").read_text())
            self.assertEqual(t["names"], ["you", "house", "random", "house:1"])
            self.assertEqual(t["by_hand"], ["you"])
            self.assertGreaterEqual(len(t["answers"]), 2)


if __name__ == "__main__":
    unittest.main()
