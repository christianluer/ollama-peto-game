.PHONY: start

# Watch the companion mailbox and talk to local Ollama.
start:
	python3 bridge.py
