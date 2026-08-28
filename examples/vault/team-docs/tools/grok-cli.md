---
tags: [tools, automation, testing, cli, setup, grok]
description: Running Grok CLI against this workspace (interactive TUI, tmux scripting, isolation, setup)
---

# Grok CLI

Grok CLI (xAI) reads `AGENTS.md` as its project bootstrap file and provides a
fullscreen TUI similar to Claude Code. This guide covers running it against this
workspace correctly and scripting it via tmux for repeatable routing tests.

## First-time setup

```bash
cd ~/context-engine

# Initialize example repos and generate index (one-time)
bash examples/setup.sh

# Verify bootstrap file exists
ls AGENTS.md

# Verify index was generated
ls examples/vault/index/
# manifest.json  team-data.json  ...
```

Grok discovers the bootstrap file at `AGENTS.md` in the project root. Use
`grok inspect` to confirm:

```bash
grok inspect
# Should show: Project Instructions → AGENTS.md (project, ~N tokens)
```

## Interactive session

Always launch from the repo root:

```bash
cd ~/context-engine
grok
```

`AGENTS.md` instructs Grok to read `examples/vault/index/manifest.json`
immediately at session start. Like Codex CLI, Grok has no hook mechanism; the
manifest enters context once via the bootstrap instruction and stays there for the
session.

**Isolation:** Grok discovers `AGENTS.md` by walking up from the working directory.
Running from `~/context-engine/` finds `AGENTS.md` and stays isolated from
sibling projects.

## Manifest injection difference vs Claude Code

Claude Code uses a `UserPromptSubmit` hook (`.claude/settings.json`) to inject the
manifest before every prompt. Grok CLI has its own hook/settings mechanism that can
be wired to do the same thing; in this example repo the hook is not configured, so
`AGENTS.md` instructs Grok to read the manifest once at session start instead.
The routing logic and manifest format are identical regardless of injection method.

## tmux: scripted interactive test

Grok's TUI does not exhibit the React Ink paste-mode issue that Claude Code has.
The safe split send-keys pattern still works and is recommended for consistency
across all CLI test scripts:

```bash
# Start Grok in this workspace
tmux new-session -d -s cetest-grok -c "$(pwd)"
tmux send-keys -t cetest-grok "grok" Enter
sleep 10   # wait for TUI init; Grok may show permission prompts on first run

# The session starts with AGENTS.md loaded; Grok reads the manifest
# automatically per the bootstrap instruction

# Query 1 — onboarding routing
tmux send-keys -t cetest-grok "How do I set up my development environment?"
sleep 0.5
tmux send-keys -t cetest-grok Enter
sleep 25
tmux capture-pane -t cetest-grok -pS -40 > /tmp/grok-q1.txt

# Query 2 — infra routing
tmux send-keys -t cetest-grok "What does the Kubernetes deployment look like?"
sleep 0.5
tmux send-keys -t cetest-grok Enter
sleep 25
tmux capture-pane -t cetest-grok -pS -40 > /tmp/grok-q2.txt

# Query 3 — data routing
tmux send-keys -t cetest-grok "What was our Q1 API latency?"
sleep 0.5
tmux send-keys -t cetest-grok Enter
sleep 25
tmux capture-pane -t cetest-grok -pS -40 > /tmp/grok-q3.txt

# Exit
tmux send-keys -t cetest-grok "/exit" Enter
sleep 3
tmux kill-session -t cetest-grok
```

## What to verify in the output

Each response should name the manifest, the slice it loaded, and the file it read,
explicitly, before answering. If Grok reads many slices or scans directories, the
routing is not working correctly. Verify `AGENTS.md` was picked up with `grok inspect`.

See `examples/reference.md` for the expected routing outcomes for each query.

## Useful flags

| Flag | Effect |
|------|--------|
| `grok "prompt"` | Start session with an initial prompt |
| `grok -p "prompt"` | Single-turn, prints response to stdout |
| `grok -c` | Continue the most recent session |
| `grok inspect` | Show what config Grok discovered for this directory |
| `grok --help` | Full flag reference |
