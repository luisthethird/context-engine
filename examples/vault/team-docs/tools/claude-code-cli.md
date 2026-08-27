---
tags: [tools, automation, testing, cli, setup]
description: Running and scripting Claude Code CLI against this workspace — interactive, print mode, and isolation
---

# Claude Code CLI

Claude Code is the primary interface for this workspace. This guide covers how to
run it correctly from the repo root, script it for automated testing, and verify
routing works as expected.

## Interactive session

Always launch from the repo root — not from inside `examples/vault/`:

```bash
cd ~/context-engine
claude
```

CLAUDE.md discovery walks up from the working directory. Launching from the repo root
finds `~/context-engine/CLAUDE.md` (the symlink to `examples/vault/CLAUDE.md`) and
the project-level `.claude/settings.json` that registers the manifest-injection hook.
If you launch from inside a subdirectory, discovery may pick up a different CLAUDE.md
or miss the hook entirely.

## Isolation from other projects

Claude Code reads CLAUDE.md by walking up from the working directory through parent
directories. Running from `~/context-engine/` walks up through `~/context-engine/`
and then `~/` — it never enters sibling directories. Any other Claude projects in
sibling directories are structurally isolated in both directions.

Project-scoped memory and history are stored under `~/.claude/projects/` keyed by
the absolute working directory path — a separate namespace per project.

## Print mode (scripted / non-interactive)

`claude -p` sends a single query, prints the response to stdout, and exits. The
`UserPromptSubmit` hook fires in print mode — manifest injection happens before every
prompt regardless of mode.

```bash
# Single query
claude -p "How do I set up my development environment?"

# Capture to file
claude -p "What was our Q1 API latency?" 2>&1 | tee /tmp/result.txt

# Multiple queries in a script (each is an independent context)
for q in \
    "How do I set up my development environment?" \
    "What does the Kubernetes deployment look like?" \
    "What was our Q1 API latency?"; do
  echo "=== $q ==="
  claude -p "$q"
  echo
done
```

Print mode tradeoff: each invocation starts a fresh context. If a follow-up query
needs the answer from the previous one, use the interactive TUI or `claude --resume`.

## Resuming a session

```bash
# The session ID is printed when you exit
claude --resume <your-session-id>
```

Resumed sessions retain the full prior context including the injected manifest.

## Verifying the hook fires

The hook prints a banner to the hook output panel before each response:

```
[context-engine] manifest loaded: 3 repos, 22 tags
[context-engine] repos: team-data, team-docs, team-infra
```

If you don't see this banner, check:
1. `~/context-engine/.claude/settings.json` exists (project-level hook registration)
2. `examples/vault/hooks/inject_manifest.py` exists
3. `examples/vault/index/claude-index-manifest.json` exists (run `bash examples/setup.sh` if not)
4. You launched Claude Code from `~/context-engine/`, not from a subdirectory

## Useful flags

| Flag | Effect |
|------|--------|
| `claude -p "prompt"` | Print mode — single query, stdout, exits |
| `claude --resume <id>` | Resume a previous session by ID |
| `claude --bare` | Skip hooks, CLAUDE.md discovery, LSP — useful for isolated debugging |
| `claude --help` | Full flag reference |

## First-time setup

```bash
cd ~/context-engine

# Initialize example repos and generate index
bash examples/setup.sh

# Verify index was generated
ls examples/vault/index/
# claude-index-manifest.json  claude-index-team-data.json  ...

# Start a session
claude
```

After setup, re-run `python3 generate_index.py --vault examples/vault --output examples/vault --split`
whenever you add new repos, directories, or files to the workspace.
