---
tags: [bootstrap, context, llm]
---
# CLAUDE.md — Workspace Context Guide

Bootstrap context for Claude Code sessions across this multi-repo workspace.
This file is loaded automatically at session start. A UserPromptSubmit hook
also injects the routing manifest — see `hooks/inject_manifest.py`.

---

## How to Find Information

This workspace uses a two-level routing index. On any task involving a file
you haven't already located:

1. Look up relevant tags in `index/claude-index-manifest.json` (already in context via hook)
2. Read only the per-repo slice(s) indicated by `tag_to_repos`
3. Navigate the slice tree to find the exact file path
4. Read that file

Do not read all slices at session start. Do not scan directories directly
when the slice already shows you the path.

**Reference files — load on demand:**

| File | LOAD WHEN |
|------|-----------|
| `index/claude-index-manifest.json` | Finding which repo/file contains info on any topic (injected automatically) |
| `index/claude-index-team-docs.json` | Working on documentation, onboarding, architecture |
| `index/claude-index-team-infra.json` | Working on infrastructure, Terraform, Kubernetes |
| `index/claude-index-team-data.json` | Working on database schemas, reports, data pipelines |
| `team-docs/index.md` | Navigation overview for the docs repo |
| `team-infra/index.md` | Navigation overview for the infra repo |
| `team-data/index.md` | Navigation overview for the data repo |
| `ways-of-working.md` | Team conventions for using this workspace and the context index |
| `team-docs/tools/tmux.md` | Scripting Claude Code via tmux — send-keys patterns, full test sequence |
| `team-docs/tools/claude-code-cli.md` | Running Claude Code against this workspace — interactive, print mode, isolation, setup |

---

## Workspace Layout

| Repo | Purpose |
|------|---------|
| `team-docs` | Onboarding guides, architecture decisions, runbooks |
| `team-infra` | Infrastructure as code: Terraform, Kubernetes configs |
| `team-data` | Database schemas, analytics reports |

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
