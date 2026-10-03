#!/usr/bin/env python3
"""Mailbox between the Peto companion chat and a local Ollama server.

Solarus quest Lua cannot open HTTP. The game writes a request file in the
Solarus write directory. This process posts that line to Ollama and writes
the reply back. Model weights stay in ~/.ollama.
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

WRITE_DIR = Path.home() / "Library/Application Support/Solarus/peto"
REQUEST = WRITE_DIR / "companion_request.txt"
REPLY = WRITE_DIR / "companion_reply.txt"
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:3b"
HEAR_YOU = "I can't hear you."

SYSTEM = (
    "You are a companion walking beside the hero in an action RPG. "
    "You do not fight. Answer in a few sentences. "
    "Do not invent the plot, the world's history, or other characters' names."
)


def read_request():
    if not REQUEST.is_file():
        return None
    text = REQUEST.read_text(encoding="utf-8")
    if not text.strip():
        return None
    request_id, _, message = text.partition("\n")
    request_id = request_id.strip()
    message = message.strip()
    if not request_id or not message:
        return None
    return request_id, message


def write_reply(request_id, body):
    WRITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = request_id + "\n" + body.replace("\r", "")
    tmp = REPLY.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(REPLY)


def ask(message):
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": message},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = data.get("message", {}).get("content", "").strip()
    return text or HEAR_YOU


def main():
    print(f"watching {WRITE_DIR}")
    while True:
        item = read_request()
        if item is None:
            time.sleep(0.2)
            continue
        request_id, message = item
        try:
            REQUEST.unlink(missing_ok=True)
        except OSError:
            time.sleep(0.2)
            continue
        try:
            reply = ask(message)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            reply = HEAR_YOU
        write_reply(request_id, reply)


if __name__ == "__main__":
    main()
