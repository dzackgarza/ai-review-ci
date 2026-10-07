# The one definition of a test file for QC target selection.
#
# Sourced (never executed) by the mypy recipes in justfiles/python.just and
# justfiles/sage.just:
#
#     source "{{artifacts}}/scripts/test-file-paths.sh"
#     is_test_file "$path" && continue
#
# Test files are never mypy targets (#456). A path is a test file when a
# directory component is `tests` or `test`, or its basename is a pytest test
# module or conftest (test_*.py, *_test.py, conftest.py) or a Sage test file
# (test_*.sage, *_test.sage, the names _sage-test-files collects). Paths are
# relative to the caller repository root.

is_test_file() {
	local path="$1"
	case "$path" in
		tests/* | */tests/* | test/* | */test/*) return 0 ;;
	esac
	case "${path##*/}" in
		test_*.py | *_test.py | conftest.py | test_*.sage | *_test.sage) return 0 ;;
	esac
	return 1
}
