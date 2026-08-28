#!/usr/bin/env python3
"""
generate_index.py - LLM context index generator

Builds a tag-routable index over a multi-repo workspace so an LLM can find
the right files out of thousands without reading everything into context.

Usage:
    python generate_index.py --vault /path/to/workspace --output . --split

See README.md for full architecture and customization guide.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── Customize these for your workspace ──────────────────────────────────────
# Map path component keywords to domain tags.
# Order matters: first match wins for the path component.
PATH_TAG_MAP = [
    ("docs",        ["docs", "documentation"]),
    ("infra",       ["infra", "infrastructure"]),
    ("scripts",     ["scripts", "automation"]),
    ("tests",       ["tests", "testing"]),
    ("kubernetes",  ["kubernetes", "k8s", "containers"]),
    ("terraform",   ["terraform", "iac", "infra"]),
    ("schemas",     ["schemas", "data", "database"]),
    ("reports",     ["reports", "analytics"]),
    ("config",      ["config", "configuration"]),
    ("ci",          ["ci", "pipelines", "devops"]),
    ("deploy",      ["deployment", "devops"]),
    ("migrations",  ["database", "migrations"]),
]

# Map filename substrings to tags (case-insensitive).
FILENAME_TAG_MAP = [
    ("Dockerfile",      ["docker", "containers"]),
    ("docker-compose",  ["docker", "containers"]),
    ("terraform",       ["terraform", "iac"]),
    ("README",          ["docs"]),
    ("CHANGELOG",       ["docs", "history"]),
    ("Makefile",        ["scripts", "automation"]),
]

# Map file extensions to tags.
EXT_TAG_MAP = {
    ".py":    ["python", "scripts"],
    ".sh":    ["scripts", "bash"],
    ".tf":    ["terraform", "iac"],
    ".yaml":  ["config"],
    ".yml":   ["config"],
    ".json":  ["config"],
    ".sql":   ["database", "schemas"],
    ".md":    ["docs"],
    ".toml":  ["config"],
}
# ────────────────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules", ".archive",
    "logs", ".DS_Store", ".obsidian", ".claude", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "build", ".next",
}

SKIP_FILES = {
    ".DS_Store", ".gitignore", ".gitattributes", ".envrc",
    ".env", "package-lock.json", "yarn.lock", "_meta.json",
}

SKIP_EXTS = {".pyc", ".pyo", ".pkl", ".pickle", ".swp", ".swo"}

# Directories with more than this many files sharing one extension
# are collapsed into a summary collection node.
COLLECTION_THRESHOLD = 20


def extract_frontmatter(path: Path) -> tuple[list[str], str]:
    """Pull tags and summary from YAML frontmatter in a markdown file."""
    tags, summary = [], ""
    try:
        text = path.read_text(errors="ignore")
        if not text.startswith("---"):
            return tags, summary
        end = text.find("---", 3)
        if end == -1:
            return tags, summary
        fm = text[3:end]
        m = re.search(r"^tags:\s*\[([^\]]*)\]", fm, re.MULTILINE)
        if m:
            tags = [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip()]
        else:
            block = re.findall(r"^tags:\s*\n((?:\s+-[^\n]+\n?)*)", fm, re.MULTILINE)
            if block:
                tags = [
                    re.sub(r"^\s*-\s*", "", ln).strip()
                    for ln in block[0].splitlines() if ln.strip()
                ]
        for field in ("description", "summary", "subtitle"):
            m = re.search(rf"^{field}:\s*(.+)", fm, re.MULTILINE)
            if m:
                summary = m.group(1).strip().strip("\"'")
                break
    except Exception:
        pass
    return tags, summary


def infer_tags(rel_path: Path, is_dir: bool = False) -> list[str]:
    """Infer tags from path components and filename."""
    tags = set()
    for part in [p.lower() for p in rel_path.parts]:
        for keyword, ktags in PATH_TAG_MAP:
            if keyword in part:
                tags.update(ktags)
    name = rel_path.name.lower()
    for keyword, ktags in FILENAME_TAG_MAP:
        if keyword.lower() in name:
            tags.update(ktags)
    if not is_dir:
        tags.update(EXT_TAG_MAP.get(rel_path.suffix.lower(), []))
    return sorted(tags)


def load_sidecar(dir_path: Path) -> dict:
    """Load _meta.json sidecar for explicit tag/summary overrides."""
    meta = dir_path / "_meta.json"
    if meta.exists():
        try:
            return json.loads(meta.read_text())
        except Exception as e:
            print(f"[context-engine] warning: malformed {meta}: {e}", file=sys.stderr)
    return {}


def file_node(path: Path, rel: Path, override: dict = None) -> dict:
    tags, summary = [], ""
    if path.suffix.lower() == ".md":
        tags, summary = extract_frontmatter(path)
    if not tags:
        tags = infer_tags(rel)
    if override:
        if override.get("tags"):
            tags = sorted(set(override["tags"]))
        summary = override.get("summary", summary)
    return {"name": path.name, "path": str(rel), "type": "file",
            "tags": sorted(set(tags)), "summary": summary}


def dir_node(dir_path: Path, vault_root: Path) -> dict:
    rel = dir_path.relative_to(vault_root)
    sidecar = load_sidecar(dir_path)
    overrides = sidecar.get("children_overrides", {})
    children = []
    file_groups: dict[str, list[Path]] = {}

    for item in sorted(dir_path.iterdir()):
        if item.is_dir():
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            children.append(dir_node(item, vault_root))
        elif item.is_file():
            if item.name in SKIP_FILES or item.name.startswith("."):
                continue
            if item.suffix.lower() in SKIP_EXTS:
                continue
            file_groups.setdefault(item.suffix.lower(), []).append(item)

    for ext, files in file_groups.items():
        if len(files) >= COLLECTION_THRESHOLD:
            # Union tags from all member files; check frontmatter on .md files
            coll_tags: set[str] = set()
            for f in files:
                coll_tags.update(infer_tags(rel / f.name))
                if f.suffix.lower() == ".md":
                    fm_tags, _ = extract_frontmatter(f)
                    coll_tags.update(fm_tags)
            children.append({
                "name": dir_path.name, "path": str(rel), "type": "collection",
                "tags": sorted(coll_tags),
                "summary": f"{len(files)} {ext} files",
                "file_count": len(files), "ext": ext,
            })
        else:
            for f in sorted(files):
                children.append(file_node(f, rel / f.name, overrides.get(f.name)))

    if sidecar.get("tags"):
        all_tags = set(sidecar["tags"])
    else:
        all_tags = set(infer_tags(rel, is_dir=True))
    for c in children:
        all_tags.update(c.get("tags", []))

    return {"name": dir_path.name, "path": str(rel), "type": "dir",
            "tags": sorted(all_tags), "summary": sidecar.get("summary", ""),
            "children": children}


def repo_node(repo_path: Path, vault_root: Path) -> dict:
    sidecar = load_sidecar(repo_path)
    node = dir_node(repo_path, vault_root)
    node["type"] = "repo"
    node["path"] = str(repo_path.relative_to(vault_root))
    if sidecar.get("summary"):
        node["summary"] = sidecar["summary"]
    return node


def discover_repos(vault_root: Path) -> list[Path]:
    return sorted(
        c for c in vault_root.iterdir()
        if c.is_dir() and (c / ".git").exists()
    )


def build_manifest(repos: list[dict]) -> dict:
    tag_to_repos: dict[str, list[str]] = {}
    repos_map = {}
    for r in repos:
        name = r["name"]
        slice_file = f"{name}.json"
        repos_map[name] = f"index/{slice_file}"
        for tag in r.get("tags", []):
            tag_to_repos.setdefault(tag, [])
            if slice_file not in tag_to_repos[tag]:
                tag_to_repos[tag].append(slice_file)
    return {
        "_schema_version": "1",
        "_usage": (
            "Load this first. Look up tags in tag_to_repos, "
            "read only the indicated slice files."
        ),
        "tag_to_repos": dict(sorted(tag_to_repos.items())),
        "repos": repos_map,
    }


def write(path: Path, data: dict, dry_run: bool):
    if dry_run:
        print(f"  [dry-run] would write {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        print(f"  written  {path}")


def main():
    parser = argparse.ArgumentParser(description="Generate LLM context index")
    parser.add_argument("--vault", required=True, help="Workspace root containing repos")
    parser.add_argument("--output", default=".", help="Output directory")
    parser.add_argument("--split", action="store_true",
                        help="Also write per-repo slices and manifest")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    out = Path(args.output).resolve()
    repos = discover_repos(vault)
    if not repos:
        print(
            f"Error: no git repos found in {vault!r}.\n"
            "Each repo must contain a .git directory.\n"
            "Run 'bash examples/setup.sh' to initialise the example workspace.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Vault : {vault}")
    print(f"Repos : {[r.name for r in repos]}")

    nodes = [repo_node(r, vault) for r in repos]
    write(out / "index.json", {"repos": nodes}, args.dry_run)

    if args.split:
        index_dir = out / "index"
        for node in nodes:
            write(
                index_dir / f"{node['name']}.json",
                {"meta": {"repo": node["name"], "split_version": "1",
                           "usage": "Per-repo slice. Load after manifest lookup."},
                 "repo": node},
                args.dry_run,
            )
        write(index_dir / "manifest.json",
              build_manifest(nodes), args.dry_run)


if __name__ == "__main__":
    main()
