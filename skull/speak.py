#!/usr/bin/env python3
"""Render the table talk: one short line per robot per moment, in its own voice.

The lines are not written by the models -- Jev, OpenJev and Luna Decisions are
single-pass choice heads and do not produce text at all. Each line is what the
move itself says out loud: a number when a bid is made, "Pass", "Skull",
"That's the bid". skull/table.py:say() is the whole vocabulary, which keeps the
voices honest: nothing is put in a robot's mouth that it did not do.

Because the vocabulary is closed, it is rendered once for every robot, and the
viewer works out which clip an event needs from the event itself. Every
recorded game gets its voices without a per-game index. Clips land in
assets/voices as MP3, with index.json listing what is there.

Uses gemini-3.8-flash-lite-tts on purpose. The full model is capped at 100
requests a day and the vocabulary is more lines than that; the lite model has
its own quota and accepts the custom voice ids all the same.

    GEMINI_API_KEY=... python3 -m skull.speak                # whatever is missing
    GEMINI_API_KEY=... python3 -m skull.speak --only Jev --max-bid 16
    python3 -m skull.speak --index-only                      # no API calls
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from skull.table import ORDER, SEATS

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "gemini-3.8-flash-lite-tts"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
CLIPS = ASSETS / "voices"
# Tier 1 allows 10 requests a minute, so pace to just under that rather than
# discovering it one 429 at a time. The server also tells you how long to wait
# when you do hit it, and that hint is worth more than any backoff curve.
PACE = 6.5
_last = [0.0]

# everything say() can ever produce. Bids can in principle reach the size of the
# table, but each line costs a request and both TTS models are capped at 100 a
# day, so --max-bid trims the tail that a real game almost never reaches.
PHRASES = ["Pass.", "Skull.", "Rose.", "That's the bid.", "That's mine, then.",
           "One to me.", "That's the game.", "I'm out."]


def vocab(max_bid: int = 16) -> list[str]:
    return ([f"{n}." for n in range(1, max_bid + 1)]
            + [f"All right. {n}." for n in range(1, max_bid + 1)]
            + PHRASES)


def clip_name(who: str, line: str) -> str:
    """The file a line lives in. index.html builds the same name from an event."""
    slug = "".join(c if c.isalnum() else "_" for c in line.lower())[:24]
    return f"{who.lower()}_{slug}.mp3"


def render(text: str, voice: str, style: str, out: Path, tries: int = 6,
           model: str | None = None) -> bool:
    wait = PACE - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    # the shape tts.py uses; an `inputs` key is rejected outright
    body = json.dumps({
        "model": model or MODEL,
        "input": [{"type": "user_input", "content": [
            {"type": "text", "text": text,
             "annotations": [{"type": "speech_metadata", "style": style}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                URL, data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
            _last[0] = time.time()
            with urllib.request.urlopen(req, timeout=180) as r:
                got = json.loads(r.read().decode())
            wav = base64.b64decode(got["steps"][0]["content"][0]["data"])
            to_mp3(wav, out)
            return True
        except urllib.error.HTTPError as e:
            msg = e.read()[:220]
            if e.code == 429 and b"per day" in msg:
                print(f"  daily quota reached; stopping ({msg!r})")
                return False
            hint = re.search(rb"retry in (\d+)s", msg)
            pause = int(hint.group(1)) + 2 if hint else 15 * (attempt + 1)
            print(f"  HTTP {e.code} on {out.name}, waiting {pause}s")
            time.sleep(pause)
        except Exception as e:
            print(f"  {type(e).__name__} on {out.name}, retrying")
            time.sleep(5)
    return False


def to_mp3(wav: bytes, out: Path) -> None:
    """A clip as the viewer loads it: mono MP3, a sixth the size of the WAV."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(wav)
        f.flush()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f.name, "-ac", "1",
                        "-c:a", "libmp3lame", "-b:a", "64k", str(out)], check=True)


def index() -> None:
    names = sorted(p.name for p in CLIPS.glob("*.mp3"))
    (CLIPS / "index.json").write_text(json.dumps(names, indent=0))
    print(f"{len(names)} clips listed in {CLIPS / 'index.json'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL,
                    help="the two TTS models have separate daily quotas")
    ap.add_argument("--max-bid", type=int, default=8)
    ap.add_argument("--only", default=None, help="seats, comma separated")
    ap.add_argument("--limit", type=int, default=120,
                    help="stop after this many requests")
    ap.add_argument("--index-only", action="store_true",
                    help="list the clips already on disk, without calling the API")
    a = ap.parse_args()
    if a.index_only:
        index()
        return
    voices = json.loads((ASSETS / "voices.json").read_text())
    seats = [x.strip() for x in a.only.split(",")] if a.only else ORDER
    made = 0
    for who in seats:
        style = SEATS[who]["voice_brief"].split(";")[0]
        for line in vocab(a.max_bid):
            out = CLIPS / clip_name(who, line)
            if out.exists():
                continue
            if made >= a.limit:
                print(f"  stopping at --limit {a.limit}")
                index()
                return
            if not render(line, voices[who], style, out, model=a.model):
                index()
                return
            made += 1
            print(f"  {who:8s} {line!r} -> {out.name}")
    index()


if __name__ == "__main__":
    main()
