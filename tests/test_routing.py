"""
Deterministic routing tests for context-engine.

These tests verify that the manifest and per-repo slices produce correct,
reproducible routing for representative queries. No LLM calls, no network,
no mocks — pure JSON reads and generate_index.py invocations.

Run:
    pytest tests/

Or with regeneration (exercises the full pipeline):
    pytest tests/ --regen
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
VAULT = REPO_ROOT / "examples" / "vault"
INDEX_DIR = VAULT / "index"
MANIFEST_PATH = INDEX_DIR / "manifest.json"


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def load_slice(slice_filename: str) -> dict:
    return json.loads((INDEX_DIR / slice_filename).read_text())


def all_paths_in_node(node: dict) -> list[str]:
    """Recursively collect all file paths from a node tree."""
    paths = []
    if node.get("type") == "file":
        paths.append(node["path"])
    for child in node.get("children", []):
        paths.extend(all_paths_in_node(child))
    return paths


def route(tags: list[str], manifest: dict) -> list[str]:
    """Return the unique set of slice filenames for the given tags."""
    seen = []
    for tag in tags:
        for slice_file in manifest["tag_to_repos"].get(tag, []):
            if slice_file not in seen:
                seen.append(slice_file)
    return seen


# ── Fixture: optionally regenerate index ─────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def maybe_regen(pytestconfig):
    if pytestconfig.getoption("regen"):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "generate_index.py"),
             "--vault", str(VAULT), "--output", str(VAULT), "--split"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"generate_index.py failed:\n{result.stderr}"


# ── Manifest structure tests ──────────────────────────────────────────────────

class TestManifestStructure:
    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), "Manifest not found — run bash examples/setup.sh"

    def test_required_fields(self):
        m = load_manifest()
        assert "_schema_version" in m
        assert "tag_to_repos" in m
        assert "repos" in m

    def test_schema_version(self):
        assert load_manifest()["_schema_version"] == "1"

    def test_all_three_repos_present(self):
        repos = load_manifest()["repos"]
        assert "team-docs" in repos
        assert "team-infra" in repos
        assert "team-data" in repos

    def test_repo_slice_files_exist(self):
        repos = load_manifest()["repos"]
        for repo_name, slice_path in repos.items():
            full = INDEX_DIR / Path(slice_path).name
            assert full.exists(), f"Slice file missing for {repo_name}: {slice_path}"

    def test_tag_values_are_lists(self):
        for tag, slices in load_manifest()["tag_to_repos"].items():
            assert isinstance(slices, list), f"tag_to_repos[{tag!r}] is not a list"
            assert len(slices) > 0, f"tag_to_repos[{tag!r}] is empty"

    def test_slice_filenames_in_tag_map_exist(self):
        m = load_manifest()
        for tag, slices in m["tag_to_repos"].items():
            for fname in slices:
                assert (INDEX_DIR / fname).exists(), \
                    f"Slice {fname!r} referenced by tag {tag!r} does not exist"


# ── Routing correctness tests ─────────────────────────────────────────────────
#
# Each scenario mirrors a real LLM query (from examples/reference.md).
# Tags represent what an LLM should derive from the natural-language question.
# Assertions verify which slice(s) are returned and which are NOT returned.

class TestRouting:
    """Query 1 — onboarding / dev-env setup → team-docs only."""

    def test_setup_tag_routes_to_docs(self):
        m = load_manifest()
        slices = route(["setup"], m)
        assert "team-docs.json" in slices

    def test_onboarding_tag_routes_to_docs(self):
        m = load_manifest()
        slices = route(["onboarding"], m)
        assert "team-docs.json" in slices

    def test_setup_does_not_route_to_infra(self):
        m = load_manifest()
        slices = route(["setup", "onboarding"], m)
        assert "team-infra.json" not in slices

    def test_setup_does_not_route_to_data(self):
        m = load_manifest()
        slices = route(["setup", "onboarding"], m)
        assert "team-data.json" not in slices

    def test_kubernetes_tag_routes_to_infra(self):
        m = load_manifest()
        slices = route(["kubernetes"], m)
        assert "team-infra.json" in slices

    def test_k8s_alias_routes_to_infra(self):
        m = load_manifest()
        slices = route(["k8s"], m)
        assert "team-infra.json" in slices

    def test_deployment_tag_routes_to_infra(self):
        m = load_manifest()
        slices = route(["deployment"], m)
        assert "team-infra.json" in slices

    def test_kubernetes_does_not_route_to_docs(self):
        m = load_manifest()
        slices = route(["kubernetes", "deployment"], m)
        assert "team-docs.json" not in slices

    def test_kubernetes_does_not_route_to_data(self):
        m = load_manifest()
        slices = route(["kubernetes", "deployment"], m)
        assert "team-data.json" not in slices

    def test_analytics_tag_routes_to_data(self):
        m = load_manifest()
        slices = route(["analytics"], m)
        assert "team-data.json" in slices

    def test_reports_tag_routes_to_data(self):
        m = load_manifest()
        slices = route(["reports"], m)
        assert "team-data.json" in slices

    def test_analytics_does_not_route_to_docs(self):
        m = load_manifest()
        slices = route(["analytics", "reports"], m)
        assert "team-docs.json" not in slices

    def test_analytics_does_not_route_to_infra(self):
        m = load_manifest()
        slices = route(["analytics", "reports"], m)
        assert "team-infra.json" not in slices


# ── Slice navigation tests ────────────────────────────────────────────────────
#
# Verify that after routing to the correct slice, the expected file paths
# are actually reachable by walking the node tree.

class TestSliceNavigation:
    def test_docs_slice_contains_onboarding(self):
        node = load_slice("team-docs.json")
        paths = all_paths_in_node(node.get("repo", node))
        assert any("onboarding" in p for p in paths), \
            f"onboarding file not found in team-docs slice. Paths: {paths}"

    def test_docs_slice_contains_tmux_tool(self):
        node = load_slice("team-docs.json")
        paths = all_paths_in_node(node.get("repo", node))
        assert any("tmux" in p for p in paths), \
            f"tmux tool file not found in team-docs slice. Paths: {paths}"

    def test_docs_slice_contains_claude_code_cli_tool(self):
        node = load_slice("team-docs.json")
        paths = all_paths_in_node(node.get("repo", node))
        assert any("claude-code-cli" in p for p in paths), \
            f"claude-code-cli tool not found in team-docs slice. Paths: {paths}"

    def test_infra_slice_contains_kubernetes(self):
        node = load_slice("team-infra.json")
        paths = all_paths_in_node(node.get("repo", node))
        assert any("kubernetes" in p for p in paths), \
            f"kubernetes path not found in team-infra slice. Paths: {paths}"

    def test_data_slice_contains_reports(self):
        node = load_slice("team-data.json")
        paths = all_paths_in_node(node.get("repo", node))
        assert any("report" in p for p in paths), \
            f"report path not found in team-data slice. Paths: {paths}"

    def test_infra_slice_repo_field_present(self):
        data = load_slice("team-infra.json")
        assert "repo" in data, "Per-repo slice missing 'repo' key"

    def test_slices_have_meta_field(self):
        for fname in ["team-docs.json", "team-infra.json",
                      "team-data.json"]:
            data = load_slice(fname)
            assert "meta" in data, f"{fname} missing 'meta' field"


# ── Tag propagation tests ─────────────────────────────────────────────────────
#
# Verify that tags set in _meta.json and frontmatter propagate correctly
# to their parent directory nodes.

class TestTagPropagation:
    def test_tools_tag_propagates_to_team_docs(self):
        m = load_manifest()
        assert "team-docs.json" in m["tag_to_repos"].get("tools", []), \
            "tools tag did not propagate to team-docs slice"

    def test_tmux_tag_propagates_to_manifest(self):
        m = load_manifest()
        assert "tmux" in m["tag_to_repos"], "tmux tag missing from manifest"

    def test_onboarding_tag_propagates_from_frontmatter(self):
        m = load_manifest()
        assert "onboarding" in m["tag_to_repos"], "onboarding tag missing — frontmatter not parsed"

    def test_kubernetes_tag_propagates_from_path(self):
        m = load_manifest()
        assert "kubernetes" in m["tag_to_repos"], \
            "kubernetes tag missing — PATH_TAG_MAP inference not working"


# ── Round-trip test ───────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not any(p.is_dir() and (p / ".git").exists()
            for p in VAULT.iterdir() if p.is_dir()),
    reason="Example repos not initialised — run 'bash examples/setup.sh' first, or use --regen"
)
class TestRoundTrip:
    """Verify that regenerating the index produces an equivalent manifest.

    Requires initialised example repos (.git dirs present in examples/vault/).
    Run with: pytest tests/ --regen
    Or initialise first: bash examples/setup.sh
    """

    def test_regenerated_manifest_matches_routing(self, tmp_path, pytestconfig):
        if pytestconfig.getoption("regen"):
            pytest.skip(
                "--regen overwrites the committed manifest before this test runs; "
                "round-trip comparison is not meaningful. Run without --regen to verify staleness."
            )
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "generate_index.py"),
             "--vault", str(VAULT), "--output", str(tmp_path), "--split"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"generate_index.py failed:\n{result.stderr}"

        regen_manifest = json.loads((tmp_path / "index" / "manifest.json").read_text())
        orig_manifest = load_manifest()

        regen_routing = {k: sorted(v) for k, v in regen_manifest["tag_to_repos"].items()}
        orig_routing = {k: sorted(v) for k, v in orig_manifest["tag_to_repos"].items()}
        assert regen_routing == orig_routing, (
            "Routing values changed — a tag maps to different repos than committed. "
            "Run: python3 generate_index.py --vault examples/vault --output examples/vault --split"
        )

        assert regen_manifest["repos"] == orig_manifest["repos"], \
            "Regenerated manifest has different repos than committed manifest."


# ── Collection-node tests ─────────────────────────────────────────────────────
#
# Verify the COLLECTION_THRESHOLD logic in generate_index.py: directories with
# >= 20 files sharing one extension collapse to a single collection node.
# These tests import from generate_index.py directly (not from committed JSON)
# to exercise the code path without requiring >=20 files in the example vault.

@pytest.fixture(scope="session")
def gen():
    spec = importlib.util.spec_from_file_location(
        "generate_index", REPO_ROOT / "generate_index.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCollectionNode:
    def test_at_threshold_collapses(self, tmp_path, gen):
        """Exactly 20 same-ext files produce one collection node."""
        vault = tmp_path / "vault"
        repo = vault / "myrepo"
        repo.mkdir(parents=True)
        for i in range(20):
            (repo / f"img_{i:02d}.png").write_text("")
        node = gen.dir_node(repo, vault)
        collections = [c for c in node["children"] if c["type"] == "collection"]
        assert len(collections) == 1
        assert collections[0]["ext"] == ".png"
        assert collections[0]["file_count"] == 20

    def test_below_threshold_expands(self, tmp_path, gen):
        """19 same-ext files remain as individual file nodes (no collection)."""
        vault = tmp_path / "vault"
        repo = vault / "myrepo"
        repo.mkdir(parents=True)
        for i in range(19):
            (repo / f"img_{i:02d}.png").write_text("")
        node = gen.dir_node(repo, vault)
        collections = [c for c in node["children"] if c["type"] == "collection"]
        assert len(collections) == 0
        file_nodes = [c for c in node["children"] if c["type"] == "file"]
        assert len(file_nodes) == 19

    def test_mixed_exts_only_large_group_collapses(self, tmp_path, gen):
        """20 .png + 5 .md: only .png collapses; .md files expand individually."""
        vault = tmp_path / "vault"
        repo = vault / "myrepo"
        repo.mkdir(parents=True)
        for i in range(20):
            (repo / f"img_{i:02d}.png").write_text("")
        for i in range(5):
            (repo / f"doc_{i}.md").write_text("---\ntags: [docs]\n---\n")
        node = gen.dir_node(repo, vault)
        collections = [c for c in node["children"] if c["type"] == "collection"]
        file_nodes = [c for c in node["children"] if c["type"] == "file"]
        assert len(collections) == 1
        assert collections[0]["ext"] == ".png"
        assert len(file_nodes) == 5
