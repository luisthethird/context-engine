---
tags: [bootstrap, context, llm]
---
# Workspace Context Guide

Bootstrap file for all CLI agents (Claude Code, Codex CLI, Grok CLI).
Loaded automatically at session start from the repo root (`~/context-engine/`).
Claude Code also injects the routing manifest before each prompt via a
`UserPromptSubmit` hook (see `examples/vault/hooks/inject_manifest.py`).
Codex CLI and Grok CLI: read `examples/vault/index/manifest.json` at session start.

---

## How to Find Information

This workspace uses a two-level routing index. On any task involving a file
you haven't already located:

1. Look up relevant tags in `examples/vault/index/manifest.json`
2. Read only the per-repo slice(s) indicated by `tag_to_repos`
3. Navigate the slice tree to find the exact file path
4. Read that file

Do not read all slices at session start. Do not scan directories directly
when the slice already shows you the path.

**Reference files (load on demand):**

| File | LOAD WHEN |
|------|-----------|
| `examples/vault/index/manifest.json` | Finding which repo/file contains info on any topic |
| `examples/vault/index/team-docs.json` | Working on documentation, onboarding, architecture |
| `examples/vault/index/team-infra.json` | Working on infrastructure, Terraform, Kubernetes |
| `examples/vault/index/team-data.json` | Working on database schemas, reports, data pipelines |
| `examples/vault/team-docs/index.md` | Navigation overview for the docs repo |
| `examples/vault/team-infra/index.md` | Navigation overview for the infra repo |
| `examples/vault/team-data/index.md` | Navigation overview for the data repo |
| `examples/vault/ways-of-working.md` | Team conventions for using this workspace and the context index |
| `examples/vault/team-docs/tools/tmux.md` | Scripting any CLI agent via tmux: send-keys patterns, full test sequences |
| `examples/vault/team-docs/tools/claude-code-cli.md` | Running Claude Code against this workspace |
| `examples/vault/team-docs/tools/codex-cli.md` | Running Codex CLI against this workspace |
| `examples/vault/team-docs/tools/grok-cli.md` | Running Grok CLI against this workspace |

---

## Workspace Layout

| Repo | Purpose |
|------|---------|
| `examples/vault/team-docs` | Onboarding guides, architecture decisions, runbooks |
| `examples/vault/team-infra` | Infrastructure as code: Terraform, Kubernetes configs |
| `examples/vault/team-data` | Database schemas, analytics reports |

---

## Index Regeneration

Run after any structural change to the workspace (new repos, new directories,
renamed files):

```bash
bash examples/setup.sh   # first time only (git init in each repo)

python3 generate_index.py \
    --vault examples/vault \
    --output examples/vault \
    --split
```

The output is committed. Agents read committed JSON, not live filesystem state.
