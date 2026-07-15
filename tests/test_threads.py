from ai_review_ci.models import finding_fingerprint
from ai_review_ci.policy_index import canonical_route, load_policy_index
from ai_review_ci.threads import parse_diff, partition_findings, pick_anchor, render_thread_body


def test_parse_diff_maps_new_side_commentable_lines() -> None:
    diff = """diff --git a/src/example.py b/src/example.py
index 1111111..2222222 100644
--- a/src/example.py
+++ b/src/example.py
@@ -10,3 +10,4 @@ def example() -> None:
 context
-old
+new
 unchanged
+extra
"""

    assert parse_diff(diff) == {"src/example.py": {10, 11, 12, 13}}


def test_parse_diff_uses_renamed_target_and_omits_deleted_files() -> None:
    diff = """diff --git a/src/old.py b/src/new.py
similarity index 88%
rename from src/old.py
rename to src/new.py
--- a/src/old.py
+++ b/src/new.py
@@ -1 +1,2 @@
 unchanged
+added
diff --git a/src/deleted.py b/src/deleted.py
deleted file mode 100644
index 3333333..0000000
--- a/src/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-deleted
"""

    assert parse_diff(diff) == {"src/new.py": {1, 2}}


def test_pick_anchor_prefers_reported_line_when_visible() -> None:
    finding = {
        "location": {
            "path": "src/example.py",
            "start_line": 11,
            "end_line": 13,
        }
    }

    assert pick_anchor(finding, {"src/example.py": {10, 12, 13}}) == 12


def test_partition_findings_skips_existing_fingerprint_threads() -> None:
    finding = {
        "tier": "tier2",
        "label": "Duplicate-shaped finding",
        "category": "DOC_CONSISTENCY",
        "location": {
            "path": "src/example.py",
            "start_line": 12,
            "end_line": 13,
        },
        "violated_invariant": "Distinct findings can share a category and path.",
        "proof_command": "review existing thread and candidate evidence",
        "symptom": "same category/path fingerprint",
        "source": "candidate review output",
        "consequence": "automatic suppression could hide a true positive",
        "pattern": "possible duplicate",
        "why_it_matters": "disposition needs semantic comparison",
        "evidence": [
            {
                "path": "src/example.py",
                "lines": [12, 13],
                "kind": "primary",
            }
        ],
    }
    fingerprint = finding_fingerprint("DOC_CONSISTENCY", "src/example.py")
    seen = {fingerprint}

    comments, off_diff, possible_duplicates = partition_findings([finding], {"src/example.py": {12}}, seen, "General Review")

    assert not comments
    assert not off_diff
    assert possible_duplicates == 1
    assert seen == {fingerprint}


def test_render_thread_body_appends_canonical_policy_guidance() -> None:
    finding = {
        "tier": "tier1",
        "label": "SLOP",
        "category": "bridge-burning",
        "policy_code": "POLICY.NO_MOCK_PROOF",
        "location": {
            "path": "src/example.py",
            "start_line": 12,
            "end_line": 13,
        },
        "violated_invariant": "Mocks cannot prove a real boundary obligation.",
        "proof_command": "review submitted report artifact",
        "pattern": "mocked proof path",
        "why_it_matters": "fake collaborators preserve success-shaped output",
        "evidence": [
            {
                "path": "src/example.py",
                "lines": [12, 13],
                "kind": "primary",
            }
        ],
    }

    body = render_thread_body(finding, "Slop Review", "a" * 64)

    route = canonical_route("POLICY.NO_MOCK_PROOF")
    remediation_text = load_policy_index().remediation_for_policy("POLICY.NO_MOCK_PROOF").required_remediation
    assert "#### Canonical catalogue route" in body
    assert f"`{route.policy_code}` → `{route.remediation_code}`" in body
    assert remediation_text not in body


def test_render_thread_body_includes_structured_reviewer_identity() -> None:
    finding = {
        "tier": "tier1",
        "label": "SLOP",
        "category": "bridge-burning",
        "location": {
            "path": "src/example.py",
            "start_line": 12,
            "end_line": 13,
        },
        "violated_invariant": "Review feedback needs a routable reviewer identity.",
        "proof_command": "inspect rendered review thread body",
        "evidence": [
            {
                "path": "src/example.py",
                "lines": [12, 13],
                "kind": "primary",
            }
        ],
    }

    body = render_thread_body(finding, "Slop Review", "b" * 64)

    assert '<!-- ai-review-reviewer: {"agent": "opencode-ai", "prompt_id": "reviews/slop", "prompt_version": "1.0.0", "type": "slop"} -->' in body
    assert "**Reviewer identity:** `type=slop; agent=opencode-ai; prompt_id=reviews/slop; prompt_version=1.0.0`" in body
