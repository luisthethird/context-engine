---
tags: [docs, conventions, workflow, context]
description: Team conventions for working in this multi-repo workspace with context-engine
---

# Ways of Working

Conventions for this workspace. These exist to keep the context index useful
and the LLM's orientation overhead low.

---

## Context Index

**Regenerate after structural changes.** Adding a repo, creating a new
directory, or significantly renaming files requires a new index run. Stale
paths in the index cause the LLM to attempt reads that fail.

**Never hand-edit the generated JSON.** `claude-index.json`,
`index/claude-index-manifest.json`, and `index/claude-index-{repo}.json`
are all script outputs. Edit `_meta.json` sidecars or frontmatter instead,
then regenerate.

**Use `_meta.json` for anything inference gets wrong.** Path-based tag
inference is the fallback. If a directory is being tagged incorrectly or
not at all, drop a `_meta.json` next to it — that takes highest priority.

**Keep tags query-shaped, not category-shaped.** Ask: would the LLM ever
search for something tagged X? If not, the tag adds noise. Specific beats
broad: `terraform` beats `infra`; `onboarding` beats `docs`.

---

## Per-Repo index.md

Each repo has an `index.md` at its root. This is the human-curated navigation
doc — a quick-reference map of what's in the repo, where things are, and
which files matter most. Update it when the repo structure changes
significantly. The generated JSON slices are for machine navigation;
`index.md` is for a human or LLM needing a quick mental model before diving
into the slice.

---

## Frontmatter

All markdown files benefit from frontmatter tags and a description:

```yaml
---
tags: [docs, onboarding]
description: New engineer setup guide
---
```

Tags here feed directly into the index with higher priority than path
inference. The `description` field becomes the node summary visible in slices.

---

## Session Start Discipline

- The manifest is injected automatically at session start via the
  `UserPromptSubmit` hook. It stays in context for the session.
- Do not re-read the manifest on every query.
- Do not read per-repo slices speculatively — only after a tag lookup
  confirms that slice contains what you need.
- When a slice shows you a file path, read that specific file. Do not
  list the directory to find alternatives unless the first path misses.

---

## Committing

The generated index is committed alongside source files. A stale index is
better than no index — it still routes correctly for unchanged paths. Just
regenerate and commit when structure changes.
