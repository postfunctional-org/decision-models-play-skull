"""A hosted model answering a Skull question, through whichever request shape
its provider uses.

    systemone   {"model", "state", "questions": {"act": {...}}}   -> answers.act.choice
    decisions   {"model", "input", "questions": [...]}            -> answers[name=act]
    anthropic   /v1/messages, one user turn, one word back        -> content[0].text

The `anthropic` shape is a generative model answering a multiple-choice question
in one word, which is not the same kind of thing as a choice head: it spends
tokens, and it returns no probabilities. Keep max_tokens small and do not turn
on thinking, or the comparison stops being a comparison.

Configuration comes from the environment, so no key reaches a command line:

    NAME_BASE_URL  NAME_API_KEY  NAME_MODEL  NAME_API  NAME_PATH

`skull.play.configure()` fills in everything but the key from skull/table.py.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class ModelAgent:
    kind = "model"

    MAX_TOKENS = 8          # one word, and no room to argue with itself

    def __init__(self, tag, base_url, api_key, model, api="systemone", path=None,
                 timeout=120.0, retries=1):
        self.name, self.base_url, self.api_key, self.model = tag, base_url.rstrip("/"), api_key, model
        self.api = api
        self.path = path or {"decisions": "/v1/decisions",
                             "anthropic": "/v1/messages"}.get(api, "/v1/systemone")
        self.timeout, self.retries = timeout, retries
        self.calls, self.errors = 0, 0

    def request(self, obs: dict) -> dict:
        crit = {c["id"]: c["desc"] for c in obs["candidates"]}
        if self.api == "anthropic":
            ids = list(crit)
            lines = [obs["instructions"], "", obs["state"], "", "Your options:"]
            lines += [f"* {k} -- {v}" for k, v in crit.items()]
            lines += ["", "Answer with exactly one word, the id of your chosen "
                      "option: " + " or ".join(f"`{i}`" for i in ids) + ". Output "
                      "nothing else -- no explanation, no punctuation, no preamble. "
                      "Your entire response must be that single word."]
            return {"model": self.model, "max_tokens": self.MAX_TOKENS,
                    "messages": [{"role": "user", "content": "\n".join(lines)}]}
        if self.api == "decisions":
            return {"model": self.model, "input": obs["state"],
                    "questions": [{"type": "choice", "name": "act",
                                   "instructions": obs["instructions"],
                                   "choices": [{"value": k, "description": v}
                                               for k, v in crit.items()]}]}
        return {"model": self.model, "state": obs["state"],
                "questions": {"act": {"type": "choice",
                                      "instructions": obs["instructions"],
                                      "criteria": crit}}}

    def answer(self, payload: dict) -> dict:
        if self.api == "anthropic":
            text = "".join(b.get("text", "") for b in payload.get("content", []))
            return {"choice": text.strip().strip("`.,'\"").split()[0]
                    if text.strip() else ""}
        if self.api == "decisions":
            a = next(x for x in payload["answers"] if x.get("name") == "act")
            probs = a.get("probabilities")
            if isinstance(probs, list):
                a = dict(a, probabilities={x["value"]: x["probability"] for x in probs})
            return a
        return payload["answers"]["act"]

    def pick(self, g, pid, obs):
        body = json.dumps(self.request(obs)).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        t0 = time.time()
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(self.base_url + self.path, data=body,
                                             method="POST", headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read().decode())
                break
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == self.retries:
                    self.errors += 1
                    raise
                time.sleep(2.0)
        self.calls += 1
        a = self.answer(payload)
        return a["choice"], {"probs": a.get("probabilities"),
                             "confidence": a.get("confidence"),
                             "latency_ms": round(1000 * (time.time() - t0), 1)}


def from_env(tag: str) -> ModelAgent:
    up = tag.upper()
    base = os.environ.get(f"{up}_BASE_URL")
    if not base:
        raise ValueError(f"set {up}_BASE_URL (and {up}_API_KEY, {up}_MODEL, {up}_API)")
    return ModelAgent(tag, base, os.environ.get(f"{up}_API_KEY") or None,
                      os.environ.get(f"{up}_MODEL", tag),
                      os.environ.get(f"{up}_API", "systemone").lower(),
                      os.environ.get(f"{up}_PATH"))
