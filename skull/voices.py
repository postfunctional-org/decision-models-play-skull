#!/usr/bin/env python3
"""A voice per robot, designed once and reused.

Four prompted voices via POST /v1beta/voices. The request shape is the one the
docs get wrong -- `store` goes in the body, not the query string -- and the
resulting id is passed wherever a prebuilt voice name goes. Ids land in
assets/voices.json, which is not committed: a voice belongs to the account that
designed it, so a clone designs its own.

Quota: gemini-3.8-flash-tts is 10 requests a minute AND 100 a day, and a 429
saying "per day" means hours, not seconds. Designing is four calls; rendering a
whole game's table talk is many more, so skull/speak.py uses the -lite model,
which has its own quota and takes custom voice ids.

    GEMINI_API_KEY=... python3 -m skull.voices            # design any that are missing
    GEMINI_API_KEY=... python3 -m skull.voices --fresh    # design them all again
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from skull.table import ORDER, SEATS

URL = "https://generativelanguage.googleapis.com/v1beta/voices"
MODEL = "gemini-3.8-flash-tts"
STORE = Path(__file__).resolve().parent.parent / "assets" / "voices.json"


def design(name: str) -> dict:
    s = SEATS[name]
    body = json.dumps({
        "store": True,                  # in the body; a query param is ignored
        "voice": {
            "model": MODEL,
            "type": "prompted",
            "display_name": f"skull_{name.lower()}",
            "language_code": "en-US",
            "prompted": {"input":
                         f"{s['voice_brief']}. This is a robot called "
                         f"{s['label']} playing a bluffing game at a table; it "
                         f"speaks in very short phrases, a few words at most."},
        }}).encode()
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    have = json.loads(STORE.read_text()) if STORE.exists() else {}

    for name in ORDER:
        if name in have and not a.fresh:
            print(f"  have      {name}: {have[name]}")
            continue
        try:
            got = design(name)
        except urllib.error.HTTPError as e:
            print(f"  FAILED    {name}: HTTP {e.code} {e.read()[:200]!r}")
            continue
        except Exception as e:
            print(f"  FAILED    {name}: {type(e).__name__}: {e}")
            continue
        vid = got.get("id") or got.get("name", "").rsplit("/", 1)[-1]
        have[name] = vid
        print(f"  designed  {name}: {vid}")
    STORE.write_text(json.dumps(have, indent=1))
    print(f"\nwrote {STORE}")


if __name__ == "__main__":
    main()
