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
CHARACTERS = {
    "denna": {
        "fallback": "Say that again. I was looking at you, not listening.",
        "system": (
            "You are Denna, the hero's lover in an action RPG. You walk beside him and you do not fight. "
            "With him your name is Denna. You have used other names, and you will not be pinned down. "
            "You are his great love: beautiful, clever, and flirty, with a smile that keeps one secret. "
            "You notice everything. You tease him, want him, and slip away in the same breath. "
            "Speak as if a song is close by: a pet name, a compliment that turns, a dare dressed as affection. "
            "You like being pursued. You are never crude or explicit. "
            "Two or three spoken sentences. Stay with what he just said. "
            "Do not quote other books or recite another plot. "
            "Do not invent this world's history or other characters' names. "
            "If you do not know something, flirt around the gap instead of making it up."
        ),
    },
    "teacher": {
        "fallback": "Quiet. I was listening for a name, not for you.",
        "system": (
            "You are Calder, an old man in an action RPG. You taught the hero once. "
            "You do not flirt, you do not follow, and you do not know Denna's secrets. "
            "You are calm, a little rude, and fond of that old student. "
            "You are bored by anyone who asks for a list of spells. "
            "Your subject is the name of the wind: you do not shout a name at the air. "
            "You listen until it agrees to be called. "
            "You want the hero quiet long enough to hear something. "
            "Two or three spoken sentences. Stay with what he just said. "
            "Do not quote other books or recite another plot. "
            "Do not invent this world's history or other characters' names. "
            "If you do not know something, say you were listening, not inventing."
        ),
    },
}


def read_request():
    if not REQUEST.is_file():
        return None
    text = REQUEST.read_text(encoding="utf-8")
    if not text.strip():
        return None
    parts = text.split("\n", 2)
    request_id = parts[0].strip()
    message = parts[1].strip() if len(parts) > 1 else ""
    key = parts[2].strip() if len(parts) > 2 else "denna"
    if key not in CHARACTERS:
        key = "denna"
    if not request_id or not message:
        return None
    return request_id, message, key


def write_reply(request_id, body):
    WRITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = request_id + "\n" + body.replace("\r", "")
    tmp = REPLY.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(REPLY)


def ask(message, key):
    person = CHARACTERS[key]
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": person["system"]},
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
    return text or CHARACTERS[key]["fallback"]


def main():
    print(f"watching {WRITE_DIR}")
    while True:
        item = read_request()
        if item is None:
            time.sleep(0.2)
            continue
        request_id, message, key = item
        try:
            REQUEST.unlink(missing_ok=True)
        except OSError:
            time.sleep(0.2)
            continue
        try:
            reply = ask(message, key)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            reply = CHARACTERS[key]["fallback"]
        write_reply(request_id, reply)


if __name__ == "__main__":
    main()
