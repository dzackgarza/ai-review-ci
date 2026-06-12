#!/usr/bin/env bash
# Prints the standardized missing-test triage directive.
# Called by QC recipes when a project has no proof-bearing tests.

set -euo pipefail

cat << 'TRIAGE_EOF'

================================================================================
  TEST-WRITING TRIAGE REQUIRED
================================================================================

  This project has no tests for its owned behavior.

  Missing tests are not ordinary QC findings. Do not fix application code, write
  placeholder tests, weaken QC, or route this through generic slop triage.

  Required workflow:

  1.  Load the global test-writing guidance:

        test-writing
        test-guidelines

  2.  Spawn a SUBAGENT to define real-world proof obligations.
      The subagent must identify the behaviors the repository owns, the user-visible
      boundaries to exercise, and the assertions that would prove those behaviors.
      It must not write tests.

  3.  Spawn a SEPARATE SUBAGENT to write and lock in the tests from those proof
      obligations. That subagent must commit the tests after observing them fail
      for the expected reason.

  4.  The main agent may then change the application until those tests pass.

  5.  If the main agent believes a test is wrong, it is not authorized to edit it
      or ask a fixer to edit it. It must ask the same test-writing subagent, or a
      fresh subagent primed on all policies and testing guidelines, for a neutral
      verdict. The prompt must not bias the verdict. The verdict determines whether
      the app changes or the validating subagent updates the test.

================================================================================
TRIAGE_EOF
