#!/usr/bin/env python3
"""
inject_manifest.py - UserPromptSubmit hook: inject the routing manifest into context.

Registered in .claude/settings.json. Runs before every prompt submission.
Outputs the manifest so Claude has the tag-to-repo routing table in context
without needing to read it manually at session start.

Only outputs when the manifest file exists. Silent on missing file so
sessions work before the first index generation run.
"""

import json
import sys
from pathlib import Path

# Resolve manifest relative to this script's location (hooks/ is in vault root)
VAULT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = VAULT_ROOT / "index" / "claude-index-manifest.json"


def main():
    if not MANIFEST_PATH.exists():
        # No manifest yet; stay silent so the session isn't disrupted
        sys.exit(0)

    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except Exception as e:
        print(f"[context-engine] manifest read error: {e}", file=sys.stderr)
        sys.exit(0)

    repo_names = list(manifest.get("repos", {}).keys())
    tag_count = len(manifest.get("tag_to_repos", {}))

    print(f"[context-engine] manifest loaded: {len(repo_names)} repos, {tag_count} tags")
    print(f"[context-engine] repos: {', '.join(repo_names)}")
    print()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
