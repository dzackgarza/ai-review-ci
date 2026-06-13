from ai_review_ci.threads import parse_diff, pick_anchor


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
