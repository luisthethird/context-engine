#!/usr/bin/env bash
# setup.sh — prepare the example workspace for use with Claude Code
#
# Run from the repo root (~/context-engine/):
#   bash examples/setup.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT="$REPO_ROOT/examples/vault"

echo "=== context-engine example setup ==="
echo ""

# 1. Git init each example repo so generate_index.py can discover them
for repo in team-docs team-infra team-data; do
  if [ ! -d "$VAULT/$repo/.git" ]; then
    git -C "$VAULT/$repo" init -q
    echo "[ok] git init: $repo"
  else
    echo "[ok] already initialized: $repo"
  fi
done

echo ""

# 2. Symlink CLAUDE.md and AGENTS.md to repo root from the same source file.
#    CLAUDE.md is picked up by Claude Code; AGENTS.md by Codex CLI and Grok CLI.
#    Both are symlinks to examples/vault/CLAUDE.md — one bootstrap, two names.
TARGET="examples/vault/CLAUDE.md"
for SYMLINK_NAME in CLAUDE.md AGENTS.md; do
  SYMLINK="$REPO_ROOT/$SYMLINK_NAME"
  if [ ! -e "$SYMLINK" ]; then
    ln -s "$TARGET" "$SYMLINK"
    echo "[ok] symlinked $SYMLINK_NAME -> $TARGET"
  else
    echo "[ok] $SYMLINK_NAME already exists at repo root"
  fi
done

echo ""

# 3. Generate the index
echo "Generating context index..."
python3 "$REPO_ROOT/generate_index.py" \
    --vault "$VAULT" \
    --output "$VAULT" \
    --split

echo ""
echo "=== setup complete ==="
echo ""
echo "To test with Claude Code CLI:"
echo "  cd $REPO_ROOT"
echo "  claude"
echo ""
echo "Claude will load CLAUDE.md from the repo root and inject the manifest"
echo "automatically on every prompt via the UserPromptSubmit hook."
echo ""
echo "This workspace is isolated from any other Claude projects in sibling"
echo "directories — no context contamination in either direction."
