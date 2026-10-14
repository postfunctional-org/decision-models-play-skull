#!/usr/bin/env python3
"""The four robots and the table they play on.

On the marks: these are not reproductions of anyone's logo. Each robot carries a
plain insignia and a colour, and the viewer prints the provider's name in text
beside it. That is enough for a viewer to tell who is playing, and it keeps the
page from passing itself off as something official.

The art in assets/ is committed, so nothing here needs to run. Each picture is
asked for once and kept; `--fresh` asks the model again.

    OPENAI_API_KEY=... python3 -m skull.art            # whatever is missing
    OPENAI_API_KEY=... python3 -m skull.art --fresh    # all of it again
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from skull.table import ORDER, SEATS

MODEL = "gpt-image-2.5-flare"            # plain gpt-image-2.5 404s
URL = "https://api.openai.com/v1/images/generations"
ASSETS = Path(__file__).resolve().parent.parent / "assets"

STYLE = ("Painted digital illustration, dark cyberpunk interior, cool neon rim "
         "lighting, muted palette with one saturated accent, slightly dystopian, "
         "no text anywhere in the image, no letters, no words, no logos of real "
         "companies, clean uncluttered composition.")

TABLE = ("A round brushed-steel table seen from slightly above, empty, in a dark "
         "low room. One caged lamp hangs over the centre casting a hard pool of "
         "light. Four plain square mats of dark rubber are set around the edge, "
         "one per seat, equally spaced. A thin strip of cyan neon runs around the "
         "wall behind. Nothing on the table. " + STYLE)


def portrait(name: str) -> str:
    s = SEATS[name]
    return (f"A single robot seated at a table, upper body and head only, facing "
            f"the viewer, three-quarter view. {s['look']}. Its chest plate carries "
            f"{s['insignia']} as an engraved insignia, small and plain. The robot's "
            f"accent colour is {s['colour']}. It is playing a card game and its "
            f"posture shows it. " + STYLE)


def generate(prompt: str, size: str) -> bytes:
    body = json.dumps({"model": MODEL, "prompt": prompt, "size": size,
                       "n": 1}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                URL, data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return base64.b64decode(json.loads(r.read())["data"][0]["b64_json"])
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(4 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    # the viewer draws these well under their full size, so a WebP at quality 90
    # is a tenth of the PNG the model sends back and looks the same on screen
    jobs = [(ASSETS / "table.webp", TABLE, "1536x1024")]
    jobs += [(ASSETS / f"seat_{n.lower()}.webp", portrait(n), "1024x1024")
             for n in ORDER]
    for path, prompt, size in jobs:
        if path.exists() and not a.fresh:
            print(f"  have      {path.name}")
            continue
        try:
            png = generate(prompt, size)
            Image.open(io.BytesIO(png)).convert("RGB").save(
                path, "WEBP", quality=90, method=6)
            print(f"  made      {path.name}")
        except Exception as e:
            print(f"  FAILED    {path.name}: {type(e).__name__}: {e}")
    print(f"\nart in {ASSETS}")


if __name__ == "__main__":
    main()
