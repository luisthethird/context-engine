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
Read manifest (~50 KB)           <- always, stays in context
    |
Tag lookup -> relevant repo(s)
    |
Read per-repo slice(s) (5-30 KB) <- targeted, one or more depending on query
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

# 2. Initialize the example repos (needed for discovery)
cd examples/vault
git -C team-docs init
git -C team-infra init
git -C team-data init
cd ../..

# 3. Generate the index
python3 generate_index.py \
    --vault examples/vault \
    --output examples/vault \
    --split

# 4. Inspect the output
cat examples/vault/index/claude-index-manifest.json
```

Pre-generated output is included in `examples/vault/index/` so you can read the
JSON without running the script first.

## How an LLM Uses This

Add to your `CLAUDE.md` (or equivalent system prompt bootstrap):

```markdown
| index/claude-index-manifest.json | Finding which file contains info on any topic |
```

At session start the LLM reads the manifest. On any file-finding task:

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
| `claude-index.json` | 300KB+ | Monolithic; authoritative for scripts |
| `index/claude-index-{repo}.json` | 5-30KB | Per-repo slice; what the LLM loads |
| `index/claude-index-manifest.json` | ~50KB | Tag routing table; entry point |

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

Large directories (>20 files of one extension) are collapsed into a
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

Tested on workspaces of 13+ repos and 3,000+ files. Manifest stays under
120 KB; routing accuracy holds as long as tags are maintained.

## Why not RAG?

RAG is the right answer when you're searching unknown territory: a corpus of customer support tickets, a document dump with no consistent structure, anything where you genuinely don't know the ontology in advance. Embeddings find semantically similar content when you can't predict what form the answer will take.

A multi-repo engineering workspace is not that problem. The files have names. The directories have conventions. An architecture decision record doesn't need to be semantically similar to the query "where are the architecture decision records?" It needs to be in `docs/adr/` with a tag that says `architecture`. Most navigation queries in a code or documentation workspace are structural, not semantic. This system is built for that case.

The practical differences matter too. RAG requires an embedding model, a vector database, and an ingestion pipeline that runs on file content. This requires a Python script and produces one JSON file. File content never leaves the machine; no embedding API is called. The index contains only paths, tags, and summaries, making it fast to set up, cheap to run, and straightforward to audit: the index is a readable file, not a black-box vector space.

Routing here is also deterministic. A tag either matches a query or it doesn't. There's no threshold to tune, no top-k to second-guess, no near-miss retrieval producing a plausible-but-wrong file. When the index says a query about Kubernetes routes to `team-infra`, it routes there every time. Regeneration is triggered only by structural changes (new file, renamed directory), not by content edits, so a stable workspace rarely needs a rebuild.

Determinism also means replayability. Any routing decision can be reproduced exactly without re-running inference or worrying about embedding model drift. You can test a query, record the route, and assert that route holds across versions. That's not possible when routing depends on a vector space that shifts every time you re-embed.

The index is a committed JSON file, which gives you version traceability that RAG cannot provide. Diff two index versions and you see exactly what structural change affected routing. Map index versions to efficiency observations over time. Regression and progression have a paper trail. A RAG system would require re-embedding the entire corpus to make the same comparison.

The approach also has room to grow in ways that the tag-routing layer alone doesn't suggest.

| | RAG | This |
|---|---|---|
| Setup | Embedding model + vector DB + pipeline | `pip install` nothing; stdlib only |
| What's indexed | File contents | Paths, tags, summaries |
| Query type | Semantic similarity | Structural navigation |
| Routing | Probabilistic (top-k) | Deterministic (tag match) |
| Replayable | No (embedding drift) | Yes (same input, same route) |
| Version traceability | Re-embed to compare | `git diff` the index |
| Reindex trigger | Content changes | Structure changes |
| Privacy | Content sent to embedding API | Nothing leaves the machine |

Where RAG wins: unstructured or unknown corpora where you can't define the tag ontology ahead of time. If you're searching ten years of Slack exports or a pile of scanned PDFs, use RAG. If you're navigating a workspace you built, use this.

## Testing with Claude Code CLI

The example workspace is self-contained and isolated from any other Claude
projects on the same machine. To test organically:

```bash
# From the repo root — not from inside examples/vault/
bash examples/setup.sh   # one-time: git init repos, symlink CLAUDE.md, generate index
claude                   # starts a Claude Code session in this workspace
```

**Isolation explained:** Claude Code discovers `CLAUDE.md` and `.claude/settings.json`
by walking up from the working directory. Running from `~/context-engine/` walks up
through `~/context-engine/` and `~/`; it never touches sibling directories or
any other project. No context leaks in either direction.

The hook in `.claude/settings.json` injects the example manifest on every prompt.
Try asking Claude to find a file related to "kubernetes" or "onboarding"; it should
route through the manifest without reading any files directly.

See **[examples/reference.md](examples/reference.md)** for worked routing traces with
Mermaid diagrams: exact hook output, tag lookups, slice navigation, and context budget
for three real queries against the example workspace.

**To adapt for your own workspace**, copy `examples/vault/` structure to your own
multi-repo directory, customize `PATH_TAG_MAP` and `FILENAME_TAG_MAP` in
`generate_index.py`, regenerate the index, and copy `.claude/settings.json` to
your workspace's `.git` root.

## Beyond This Repository

This repository publishes the foundational routing layer of a larger system. A more extensive private implementation exists and formal IP protection is in progress. The public release is intentional: the indexing and injection primitives here stand on their own, and publishing them separately keeps the boundary between open and proprietary clean. Anyone interested in the broader work is welcome to reach out directly.

## Requirements

Python 3.10+, standard library only. No dependencies to install.

## License

MIT
