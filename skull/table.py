"""Who is at the table: four models, four robots, four voices.

`label` is the name a model is given in its own prompt ("You are LUNA-6"), and
it stays exactly as it was when the recorded games were played. `shown` is the
name on the charts. index.html keeps its own copy of the shown names, the
providers and the colours.

The mark is not a reproduction of anyone's logo. Each seat names the provider in
text and carries a plain insignia and a colour, which is enough for a viewer to
tell who is playing without the page passing itself off as anything official.
"""

from __future__ import annotations

SEATS = {
    "Jev": {
        "label": "Jev",
        "shown": "Jev",
        "provider": "TypeSafe · decision model",
        "colour": "#46B3A3",
        "insignia": "a bracketed check mark",
        "look": ("a small courier robot, teal panels, a narrow visor, one arm "
                 "folded behind its back like a card player keeping a tell hidden"),
        "voice_brief": ("a quick, clipped, confident young voice; sounds like it has "
                        "already decided; faint mechanical edge"),
        "api": {"env": "JEV", "base": "https://api.typesafe.ai",
                "model": "jev-1.13.0", "shape": "systemone"},
    },
    "OpenJev": {
        "label": "OpenJev",
        "shown": "OpenJev",
        "provider": "independent · open weights",
        "colour": "#7BD389",
        "insignia": "a bracketed check mark, unfilled",
        "look": ("a heavy freight robot, green plating, blocky shoulders, short "
                 "legs, sits too low at the table"),
        "voice_brief": ("a slow, heavy, deliberate voice, lower pitched, takes its "
                        "time; the sound of something large thinking"),
        # open weights with no hosted API: serve it yourself and point
        # OPENJEV_BASE_URL at the server. Loopback needs no key.
        "api": {"env": "OPENJEV", "base": "http://127.0.0.1:3111",
                "model": "openjev", "shape": "systemone"},
    },
    "LUNA": {
        "label": "LUNA-6",
        "shown": "Luna Decisions",
        "provider": "OpenAI · decision model",
        "colour": "#5BE9D0",
        "insignia": "a six-spoked rosette",
        "look": ("a slim pale robot with a flat visor band, clean and "
                 "undecorated, sits very upright"),
        "voice_brief": ("a smooth, even, almost pleasant voice, careful diction, "
                        "neutral warmth, never hurried"),
        "api": {"env": "LUNA", "base": "https://api.openai.com",
                "model": "gpt-6-luna", "shape": "decisions",
                "key": "OPENAI_API_KEY"},
    },
    "Haiku": {
        "label": "HAIKU-4",
        "shown": "Haiku 4.5",
        "provider": "Anthropic · LLM",
        "colour": "#D97757",
        "insignia": "an eight-rayed burst",
        "look": ("a compact amber robot, rounded casing, a single wide lens, "
                 "leans forward on its elbows"),
        "voice_brief": ("a light, dry, slightly amused voice, mid pitch, the "
                        "timing of someone who finds the game funny"),
        # a language model answering in one word over /v1/messages: the control
        "api": {"env": "HAIKU", "base": "https://api.anthropic.com",
                "model": "claude-haiku-4-5-20251001", "shape": "anthropic",
                "key": "ANTHROPIC_API_KEY"},
    },
}
ORDER = ["Jev", "OpenJev", "LUNA", "Haiku"]

# the scripted players, and anyone playing by hand, sit at the same table, so
# anything the viewer or the prompts ask for has to answer for them too
DEFAULT = {"label": "UNIT", "shown": "unit", "provider": "scripted",
           "colour": "#9AA7B0", "insignia": "a plain circle",
           "look": "a plain bipedal robot", "voice_brief": "flat, mechanical, unhurried",
           "api": None}


def seat(name: str) -> dict:
    """What we know about whoever is in this seat, model or bar."""
    if name in SEATS:
        return SEATS[name]
    return {**DEFAULT, "label": name.upper().replace(":", "-"), "shown": name}


def say(event: dict) -> str | None:
    """What the robot says out loud, if anything. Short, and only the moments."""
    k = event["kind"]
    if k == "opens":
        return f"{event['bid']}."
    if k == "raises":
        return {1: "One.", 2: "Two.", 3: "Three."}.get(event["bid"], f"{event['bid']}.")
    if k == "passes":
        return "Pass."
    if k == "challenge":
        return f"All right. {event['bid']}."
    if k == "flips":
        if event["disc"] == "skull":
            return "Skull."
        return "Rose." if event["count"] < event["bid"] else "That's the bid."
    if k == "fails":
        return "That's mine, then."
    if k == "wins_round":
        return "One to me." if event["points"] == 1 else "That's the game."
    if k == "eliminated":
        return "I'm out."
    return None
