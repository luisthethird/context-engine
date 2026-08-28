[![CI](https://github.com/luisthethird/context-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/luisthethird/context-engine/actions/workflows/ci.yml)

# context-engine

A tag-routable context index for LLM workspaces. Lets an AI agent find the
right files out of thousands without loading everything into context.

## The Problem

When an LLM works across a large multi-repo workspace, the naive approach is
to load all file paths (or worse, all file contents) into context. This fails
two ways: token budgets overflow, and irrelevant content degrades reasoning.

The solution is a **two-level routing index**:

```
Session start
    |
Read manifest                    <- always, stays in context
    |
Tag lookup -> relevant repo(s)
    |
Read per-repo slice(s)           <- targeted, one or more depending on query
    |
Read specific files              <- on demand, depth varies by task
```

The manifest is a small JSON file mapping tags to per-repo slice filenames.
Each slice is a tree of nodes (files, directories, collections) for one repo.
An LLM navigates this tree to find exact file paths before reading anything.

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/luisthethird/context-engine
cd context-engine

# 2. Initialize example repos and generate the index
bash examples/setup.sh

# 3. Inspect the output
cat examples/vault/index/manifest.json
```

Pre-generated output is included in `examples/vault/index/` so you can read the
JSON without running the script first.

## How an LLM Uses This

Add to your `CLAUDE.md` (or equivalent system prompt bootstrap):

```markdown
| index/manifest.json | Finding which file contains info on any topic |
```

For Claude Code, the manifest is injected before every prompt via the `UserPromptSubmit`
hook in `.claude/settings.json`. For Codex CLI and Grok CLI, the `AGENTS.md` bootstrap
instructs the agent to read it once at session start; it stays available for all
subsequent queries in that session. On any file-finding task:

1. Identify 1-3 relevant tags for the topic
2. Look up those tags in `manifest.tag_to_repos`
3. Read only the indicated per-repo slice(s)
4. Navigate the slice tree to find the exact file path
5. Read that file

See `examples/vault/CLAUDE.md` for a complete example of how this integrates
into a real workspace bootstrap file.

## Customization

`generate_index.py` has three maps to customize for your workspace. Everything
else is invariant. Do not change the node schema or manifest schema, as the
LLM consumption protocol depends on them.

### PATH_TAG_MAP

Maps path component keywords to domain tags:

```python
PATH_TAG_MAP = [
    ("docs",       ["docs", "documentation"]),
    ("terraform",  ["terraform", "iac", "infra"]),
    ("schemas",    ["schemas", "data", "database"]),
    # add your own...
]
```

### FILENAME_TAG_MAP

Maps filename substrings to tags:

```python
FILENAME_TAG_MAP = [
    ("Dockerfile",     ["docker", "containers"]),
    ("docker-compose", ["docker", "containers"]),
    # add your own...
]
```

### _meta.json Sidecar

Place a `_meta.json` in any directory to override tags and summaries:

```json
{
  "tags": ["finance", "ledger"],
  "summary": "Transaction ledgers for all accounts",
  "children_overrides": {
    "checking.csv": {
      "tags": ["finance", "checking"],
      "summary": "Checking account transactions"
    }
  }
}
```

### YAML Frontmatter

`.md` files with YAML frontmatter are parsed automatically:

```yaml
---
tags: [docs, onboarding]
description: New engineer setup guide
---
```

## Architecture

### Index Artifacts

| Artifact | Size | Purpose |
|----------|------|---------|
| `index.json` | varies | Monolithic; authoritative for scripts |
| `index/{repo}.json` | 2-30KB | Per-repo slice; what the LLM loads |
| `index/manifest.json` | <2KB–120KB | Tag routing table; entry point |

### Node Types

Every file, directory, and repo is a node:

```json
{ "name": "onboarding.md", "path": "team-docs/docs/onboarding.md",
  "type": "file", "tags": ["docs", "onboarding"], "summary": "..." }

{ "name": "docs", "path": "team-docs/docs",
  "type": "dir",  "tags": ["docs"], "summary": "", "children": [...] }

{ "name": "assets", "path": "team-docs/assets",
  "type": "collection", "tags": ["docs"], "file_count": 47, "ext": ".png" }
```

Large directories (20 or more files of one extension) are collapsed into a
`collection` node to keep slices compact.

### Tag Propagation

Tags bubble upward: a directory's tags include the union of all its children's
tags. A tag present anywhere in a repo subtree will appear in the manifest's
routing table for that repo.

### Tag Sources (priority order)

1. `_meta.json` sidecar: explicit overrides, highest priority
2. YAML frontmatter: `tags:` and `description:` fields in `.md` files
3. Path + filename inference via `PATH_TAG_MAP` and `FILENAME_TAG_MAP`

### Scope and Limits

This system does **not**:
- Index file contents (no full-text search, no semantic embeddings)
- Replace reading files; it routes to them, not away from them
- Stay current automatically; regenerate after structural changes
- Handle encrypted repos

It does one thing: route an LLM to the right files out of thousands
without reading thousands of file paths. That is the entire value.

Tested on workspaces of 13+ repos and 3,000+ files (in the author's private workspace).
Manifest stays under 120 KB; routing accuracy holds as long as tags are maintained.

## Why not RAG?

RAG is the right answer when you're searching unknown territory: a corpus of customer support tickets, a document dump with no consistent structure, anything where you genuinely don't know the ontology in advance. Embeddings find semantically similar content when you can't predict what form the answer will take.

A multi-repo engineering workspace is not that problem. The files have names. The directories have conventions. An architecture decision record doesn't need to be semantically similar to the query "where are the architecture decision records?" It needs to be in `docs/adr/` with a tag that says `architecture`. Most navigation queries in a code or documentation workspace are structural, not semantic. This system is built for that case.

The practical differences matter too. RAG requires an embedding model, a vector database, and an ingestion pipeline that runs on file content. This system requires a Python script and produces one JSON file. The index contains only paths, tags, and summaries, making it fast to set up, cheap to run, and straightforward to audit: the index is a readable file, not a black-box vector space.

Routing is deterministic given a tag set. A tag either matches a query or it doesn't. There's no threshold to tune, no top-k to second-guess, no near-miss retrieval producing a plausible-but-wrong file. When the index says a query about Kubernetes routes to `team-infra`, it routes there every time. Tag selection itself is done by an LLM inferring tags from a natural-language query, which is stochastic — the determinism lives in the lookup layer, not the inference layer. Regeneration is triggered only by structural changes (new file, renamed directory), not by content edits, so a stable workspace rarely needs a rebuild.

The index is a committed JSON file, which gives you version traceability tied to structure, not content. Diff two index versions and you see exactly what structural change affected routing — a new tag, a renamed directory, a file added to a previously empty repo. That comparison doesn't require re-running any pipeline.

| | RAG | This |
|---|---|---|
| Setup | Embedding model + vector DB + pipeline | `pip install` nothing; stdlib only |
| What's indexed | File contents | Paths, tags, summaries |
| Query type | Semantic similarity | Structural navigation |
| Routing | Probabilistic (top-k) | Deterministic (tag match) |
| Version traceability | Re-embed corpus to compare routing behavior | `git diff` the index — structural changes are directly readable |
| Reindex trigger | Content changes | Structure changes only |

Where RAG wins: unstructured or unknown corpora where you can't define the tag ontology ahead of time. If you're searching ten years of Slack exports or a pile of scanned PDFs, use RAG. If you're navigating a workspace you built, use this.

### Why not grep?

Agent CLIs ship with ripgrep and glob. Why not just `rg -l kubernetes`?

It works — until it doesn't. `rg -l kubernetes` on this repo returns 9 files: the test suite, the indexer source, the reference doc, three generated JSON index files, and three actual Kubernetes documentation files. The agent has to read all of them to determine which are the docs it should load. That's a tool round-trip per query, plus disambiguation work that eats context.

The context engine does that disambiguation once, at index time. A query tagged `kubernetes` routes directly to `team-infra.json`, which already knows which files are the Kubernetes docs. No tool call, no content read to filter, no context spent on generated artifacts. The advantage compounds: `rg` requires knowing the search term, matches literal text not concepts, and returns everything in the workspace including files you generated, not files you authored. Structural routing is cheaper, quieter, and doesn't require the query to contain the file's exact words.

## Testing and linting

The test suite verifies routing correctness without invoking any LLM: pure Python
assertions against the committed JSON manifest and slices:

```bash
# Install dev dependencies (pinned via pyproject.toml)
pip install -e ".[dev]"

# Run routing tests (35 tests — manifest structure, routing, navigation, round-trip, collection-node)
pytest tests/

# Regenerate index then run tests (exercises the full pipeline)
# Note: --regen rewrites examples/vault/index/ in place; the round-trip test
# is skipped automatically (the autouse fixture overwrites the committed manifest
# before the comparison would run, making it tautological).
pytest tests/ --regen

# Lint Python files
ruff check generate_index.py examples/vault/hooks/inject_manifest.py tests/
```

Tests are organized by concern:

| Class | What it tests |
|-------|--------------|
| `TestManifestStructure` | Required fields, schema version, slice files exist |
| `TestRouting` | All three example queries route to the correct repo and no others |
| `TestSliceNavigation` | Expected files reachable by walking the node tree |
| `TestTagPropagation` | Tags from `_meta.json` and frontmatter appear in the manifest |
| `TestRoundTrip` | Regenerated manifest routing values match committed manifest exactly |
| `TestCollectionNode` | Directories with ≥20 same-extension files collapse to a collection node; below threshold they don't |

## Provider agnosticism

This system works with Claude Code, Codex CLI, and Grok CLI. The routing index
format is provider-neutral: plain JSON read by the LLM, not an API feature.

| CLI | Bootstrap file | Manifest injection (this repo) |
|-----|---------------|-------------------------------|
| Claude Code | `CLAUDE.md` | Hook: `UserPromptSubmit` in `.claude/settings.json` injects on every prompt |
| Codex CLI | `AGENTS.md` | Bootstrap-read: agent reads manifest at session start per `AGENTS.md` instruction |
| Grok CLI | `AGENTS.md` | Bootstrap-read: agent reads manifest at session start per `AGENTS.md` instruction |

Each CLI has its own hook/settings system that can wire per-prompt injection equivalent
to Claude Code's. This example repo uses the Claude Code hook and AGENTS.md bootstrap
as the minimum viable cross-CLI setup. A full implementation can register equivalent
hooks in each CLI's config to achieve per-prompt injection for all three.

`AGENTS.md` at the repo root serves as the bootstrap for Codex CLI and Grok CLI.
It instructs the agent to read `examples/vault/index/manifest.json`
before answering any query.

**Isolation:** Each CLI discovers its bootstrap file by walking up from the working
directory. Running from `~/context-engine/` walks up through `~/context-engine/`
and `~/`; it never enters sibling directories. Projects in sibling directories are
isolated in both directions regardless of which CLI is used.

To test with Codex CLI or Grok CLI:

```bash
# One-time setup
bash examples/setup.sh

# Codex CLI
codex   # reads AGENTS.md; agent reads manifest at session start

# Grok CLI — verify bootstrap discovery first
grok inspect   # should show: AGENTS.md (project, ~N tokens)
grok           # reads AGENTS.md; agent reads manifest at session start
```

See `examples/vault/team-docs/tools/` for per-CLI tmux scripting guides and full
interactive test sequences.

See **[examples/reference.md](examples/reference.md)** for worked routing traces with
Mermaid diagrams: exact hook output, tag lookups, slice navigation, and context budget
for three real queries against the example workspace.

**To adapt for your own workspace**: copy `examples/vault/` structure to your own
multi-repo directory, customize `PATH_TAG_MAP` and `FILENAME_TAG_MAP` in
`generate_index.py`, and regenerate the index. Then copy `.claude/settings.json`
and `AGENTS.md` to your workspace root and update the paths inside both files
(change `examples/vault/` to your actual vault path).

## Beyond This Repository

This repository publishes the foundational routing layer of a larger system. A more extensive private implementation exists; the architecture extends into areas not published here. The public release is intentional: the indexing and injection primitives here stand on their own, and publishing them separately keeps the boundary between open and proprietary clean. Anyone interested in the broader work is welcome to reach out directly.

## Requirements

Python 3.10+, standard library only. No dependencies to install.

## License

MIT
