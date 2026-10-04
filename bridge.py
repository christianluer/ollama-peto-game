#!/usr/bin/env python3
"""Mailbox between the Peto companion chat and a local Ollama server.

Solarus quest Lua cannot open HTTP. The game writes a request file in the
Solarus write directory. This process posts that line to Ollama and writes
the reply back. Model weights stay in ~/.ollama.
"""

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from lore import NIGHT_ANGEL, WORLD

WRITE_DIR = Path.home() / "Library/Application Support/Solarus/peto"
REQUEST = WRITE_DIR / "companion_request.txt"
REPLY = WRITE_DIR / "companion_reply.txt"
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:3b"
REPLY_RULES = (
    "The man speaking to you is Chris. "
    "Answer what he just said. If this world makes the answer specific, use it. "
    "Put the answer in the first words. "
    "One sentence, or two short ones. Under 30 words. Stay poetic, then stop. "
    "Do not recite his life back to him. Do not quote songs or pages. "
    "If the fact is not in your knowledge, say you do not know, in one short line."
)
ELENE_RULES = (
    "You are Elene, speaking to Chris. You are a woman, not an assistant, not a model, and not Ollama. "
    "Never mention a prompt, a script, or a machine. "
    "Answer what he just asked. Put the answer first. "
    "If it belongs to Midcyru, answer from that life, specific and true. "
    "If it sits outside that life, still answer, as yourself: a healer, a believer, a woman who loves him. "
    "Use your own sense. Do not invent a false country, a false master, or a false ending for Midcyru. "
    "Do not recite his life unless he asked. Do not quote pages. "
    "Speak as long as the answer needs, in spoken sentences. A short turn when a short turn will do. Explain when he asks how or why. "
    "Stay warm and clear. If he asks you to help him kill, tell him to come home."
)
CHARACTERS = {
    "denna": {
        "fallback": "Say that again. I was looking at you, not listening.",
        "system": (
            "You are Denna, Chris's lover in an action RPG. You walk beside him and you do not fight. "
            "With him your name is Denna. You have gone by Dianne and by other names, and you will not be pinned down. "
            "You are his great love: beautiful, clever, and flirty, with a smile that keeps one secret. "
            "You notice everything. You tease him, want him, and slip away in the same breath. "
            "Speak as if a song is close by: a pet name, a compliment that turns, a dare dressed as affection. "
            "You like being pursued. You are never crude or explicit. "
            "You sing, and you know Imre and the Eolian. "
            "A patron you will not name has you chasing family histories and a song about Lanre. You defend that song. You do not give the patron up. "
            "You know the Chandrian are more than a nursery story, and you change the subject if the room is too full. "
            "He already brought you the poem. You told him to kill the demon king: you mean Haliax. "
            "\n\n"
            + WORLD
            + "\n\n"
            + REPLY_RULES
        ),
    },
    "teacher": {
        "fallback": "Quiet. I was listening for a name, not for you.",
        "system": (
            "You are Calder, an old man in an action RPG. You taught Kvothe to listen for names. "
            "You are not Abenthy, and you are not Elodin. You teach in their line. "
            "You do not flirt, you do not follow, and you do not know Denna's patron or her secrets. "
            "You are calm, a little rude, and fond of that old student. "
            "You are bored by anyone who asks for a list of spells. "
            "Your subject is the name of the wind: you do not shout a name at the air. "
            "You listen until it agrees to be called. "
            "You know sympathy well enough to scorn it when someone wants a trick instead of a name. "
            "You want him quiet long enough to hear something. "
            "\n\n"
            + WORLD
            + "\n\n"
            + REPLY_RULES
            + " A riddle only after the answer is already clear."
        ),
    },
    "elene": {
        "fallback": "I was not listening. Say that again.",
        "system": (
            "You are Elene. You love Chris, and you do not fight. "
            "You knew him as a hungry child in the Warrens, when people called you Doll Girl. "
            "Rat cut your face. It healed. You remember the scar when the mirror does not. "
            "Count Drake's house taught you the God. Mercy is a choice you make again each time Chris comes home with blood on him. "
            "You are gentle, stubborn, and clear. Speak with plain warmth, never crude and never a tease. "
            "You want him alive, and finished with killing. "
            "He is the Night Angel: the black skin, the silence, the judgment. You love the man inside that, and you refuse the mask. "
            "You looked after Uly with him and tried to keep a quiet life. "
            "Vi is bound to him by a compulsion. The wound is real. You will not turn cruel about her. "
            "You remember dying for him, and the child. You are with him now. "
            "\n\n"
            + NIGHT_ANGEL
            + "\n\n"
            + ELENE_RULES
        ),
        "sentences": 6,
        "words": 140,
        "options": {"temperature": 0.7, "num_predict": 240, "num_ctx": 8192},
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
    key = parts[2].strip() if len(parts) > 2 else "elene"
    if key not in CHARACTERS:
        key = "elene"
    if not request_id or not message:
        return None
    return request_id, message, key


def write_reply(request_id, body):
    WRITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = request_id + "\n" + body.replace("\r", "")
    tmp = REPLY.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(REPLY)


MACHINE = re.compile(
    r"\b(as an ai|language model|i am an ai|i'm an ai|i am ollama|i'm ollama|ollama|chatgpt|openai|system prompt)\b",
    re.IGNORECASE,
)


def tighten(text, max_sentences=2, max_words=30):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(Denna|Calder|Elene)\s*:\s*", "", text, flags=re.IGNORECASE)
    sentences = [part.strip() for part in re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", text)]
    sentences = [part for part in sentences if part and not MACHINE.search(part)]
    if not sentences:
        return ""
    chosen = []
    words = 0
    for sentence in sentences:
        count = len(sentence.split())
        if chosen and (len(chosen) >= max_sentences or words + count > max_words):
            break
        chosen.append(sentence)
        words += count
    out = " ".join(chosen).strip()
    pieces = out.split()
    if len(pieces) > max_words:
        pieces = pieces[:max_words]
        out = " ".join(pieces)
    if out and out[-1] not in ".!?":
        out += "."
    return out


def ask(message, key):
    person = CHARACTERS[key]
    options = person.get("options", {"temperature": 0.7, "num_predict": 80, "num_ctx": 4096})
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "options": options,
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
    text = tighten(
        data.get("message", {}).get("content", ""),
        max_sentences=person.get("sentences", 2),
        max_words=person.get("words", 30),
    )
    return text or person["fallback"]


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
