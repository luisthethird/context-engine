---
tags: [tools, automation, testing, tmux, cli]
description: Driving Claude Code's interactive TUI from tmux for scripted testing and automation
---

# tmux: Scripted Interactive Testing

tmux lets you drive Claude Code's interactive TUI from scripts, automating routing
queries, capturing responses, and running repeatable test sequences without leaving
the terminal.

## The core pattern

Claude Code's input field is a React Ink component. When text and Enter arrive in
one atomic tmux `send-keys` call they look like a paste; React Ink treats the
embedded Enter as a newline rather than a submit. The fix is to split them:

```bash
# 1. Send the text — no Enter
tmux send-keys -t mysession "How do I set up my development environment?"

# 2. Let the input field settle
sleep 0.5

# 3. Submit
tmux send-keys -t mysession Enter
```

Short strings and slash commands (`/exit`, `q`) are unaffected and work with
the combined form because they are processed before the paste threshold.

## Input field control

| Goal | Command |
|------|---------|
| Clear the input field | `tmux send-keys -t mysession "" C-u` |
| Cancel without submitting | `tmux send-keys -t mysession "" C-c` |
| Exit the session | `tmux send-keys -t mysession "/exit" Enter` |
| Resume a previous session | `claude --resume <session-id>` (at the shell) |

Claude Code shows a pre-filled suggestion after each response. Always `C-u` before
sending the next query or the queries will concatenate.

## Capturing responses

```bash
# Capture last N lines of pane output
tmux capture-pane -t mysession -pS -50

# Write to file
tmux capture-pane -t mysession -pS -100 > /tmp/test-output.txt
```

If the response is still streaming, add a `sleep` before capturing.

## Full test sequence

```bash
# Start Claude Code in this workspace (from repo root)
tmux new-session -d -s cetest -c "$(pwd)"  # run from repo root
tmux send-keys -t cetest "claude" Enter
sleep 8   # wait for TUI to initialize and trust prompt if first run

# Query 1 — onboarding routing
tmux send-keys -t cetest "How do I set up my development environment?"
sleep 0.5
tmux send-keys -t cetest Enter
sleep 20
tmux capture-pane -t cetest -pS -30 > /tmp/q1.txt

# Clear pre-fill and send query 2 — infra routing
tmux send-keys -t cetest "" C-u
tmux send-keys -t cetest "What does the Kubernetes deployment look like?"
sleep 0.5
tmux send-keys -t cetest Enter
sleep 20
tmux capture-pane -t cetest -pS -30 > /tmp/q2.txt

# Clear and query 3 — data routing
tmux send-keys -t cetest "" C-u
tmux send-keys -t cetest "What was our Q1 API latency?"
sleep 0.5
tmux send-keys -t cetest Enter
sleep 20
tmux capture-pane -t cetest -pS -30 > /tmp/q3.txt

# Exit
tmux send-keys -t cetest "" C-u
tmux send-keys -t cetest "/exit" Enter
sleep 3
tmux kill-session -t cetest
```

## What to verify in the output

Each response should name the slice it loaded and the file it read, explicitly,
before answering. If it lists many files or says "I'll search the workspace," the
routing is not working. The hook banner `[context-engine] manifest loaded: N repos,
M tags` should appear in the hook output panel before each response.

See `examples/reference.md` for the expected output of each query against this
example workspace.
