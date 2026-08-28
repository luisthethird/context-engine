---
tags: [tools, automation, testing, cli, setup, codex]
description: Running Codex CLI against this workspace (interactive TUI, tmux scripting, isolation, setup)
---

# Codex CLI

Codex CLI (OpenAI) is an alternative agentic CLI that reads `AGENTS.md` as its project
bootstrap file. This guide covers running it against this workspace correctly and scripting
it via tmux for repeatable routing tests.

## First-time setup

```bash
cd ~/context-engine

# Initialize example repos and generate index (one-time)
bash examples/setup.sh

# Verify bootstrap file exists
ls AGENTS.md
# AGENTS.md

# Verify index was generated
ls examples/vault/index/
# manifest.json  team-data.json  ...
```

## Interactive session

Always launch from the repo root:

```bash
cd ~/context-engine
codex
```

Codex reads `AGENTS.md` at session start. That file instructs it to read
`examples/vault/index/manifest.json` before answering any query. Codex CLI
has its own hook/settings mechanism for per-prompt injection; in this example
repo, `AGENTS.md` bootstrap is used instead (read once at session start).

**Isolation:** Codex reads project config by walking up from the working directory.
Running from `~/context-engine/` finds `AGENTS.md` and stays isolated from sibling
projects in both directions.

## Manifest injection difference vs Claude Code

Claude Code uses a `UserPromptSubmit` hook (`.claude/settings.json`) to inject the
manifest before every prompt. Codex CLI has its own hook/settings mechanism; in this
example repo the hook is not configured, so `AGENTS.md` instructs Codex to read the
manifest once at session start instead. The manifest stays in context for the duration
of the session; routing works the same way regardless of injection method.

## tmux: scripted interactive test

Codex's TUI is not React Ink; it does not share the same paste-mode issue that
Claude Code has. The split send-keys pattern (text, sleep, Enter) is still the
safe approach, but combined single-call sends also work reliably:

```bash
# Start Codex in this workspace
tmux new-session -d -s cetest-codex -c "$(pwd)"
tmux send-keys -t cetest-codex "codex" Enter
sleep 10   # wait for TUI init; first run may take longer during login/setup

# The session starts with AGENTS.md loaded; Codex should read the manifest
# automatically per the bootstrap instruction — no extra prompt needed

# Query 1 — onboarding routing
tmux send-keys -t cetest-codex "How do I set up my development environment?"
sleep 0.5
tmux send-keys -t cetest-codex Enter
sleep 25   # allow time for manifest read + response
tmux capture-pane -t cetest-codex -pS -40 > /tmp/codex-q1.txt

# Query 2 — infra routing
tmux send-keys -t cetest-codex "What does the Kubernetes deployment look like?"
sleep 0.5
tmux send-keys -t cetest-codex Enter
sleep 25
tmux capture-pane -t cetest-codex -pS -40 > /tmp/codex-q2.txt

# Query 3 — data routing
tmux send-keys -t cetest-codex "What was our Q1 API latency?"
sleep 0.5
tmux send-keys -t cetest-codex Enter
sleep 25
tmux capture-pane -t cetest-codex -pS -40 > /tmp/codex-q3.txt

# Exit
tmux send-keys -t cetest-codex "/exit" Enter
sleep 3
tmux kill-session -t cetest-codex
```

## What to verify in the output

Each response should name the slice it loaded and the file it read, explicitly,
before answering. If it reads the whole manifest inline or scans directories, the
routing is working but not optimally; the bootstrap instruction may need stronger
wording. If it ignores the manifest entirely, the AGENTS.md was not picked up;
verify you launched from `~/context-engine/` and the file exists.

See `examples/reference.md` for the expected routing outcomes for each query.

## Useful flags

| Flag | Effect |
|------|--------|
| `codex "prompt"` | Start session with an initial prompt |
| `codex exec "prompt"` | Non-interactive single-turn |
| `codex -c` | Continue the most recent session |
| `codex --help` | Full flag reference |
