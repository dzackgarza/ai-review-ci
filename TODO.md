Findings from the wiring check
Mutating, not fail-loud. test (pre-commit) calls _normalize-common → _format-structured-text (prettier --write, flowmark) + _semgrep --autofix, then _normalize → ruff check --fix + ruff format. Same is reachable from test-ci (pre-push). None of these use --check; they --write/--fix as a side-effect of the gate and exit 0. Result: every commit silently mutates files, the formatter output was never staged, and the worktree goes dirty after the commit has landed.
Scope leak already present. The agent's quote confirms the formatter "rewrote a large set of unrelated tracked files across the repository (including the submodule)." That's a real boundary bug — formatters must not cross the submodule boundary; this is also a violation of the project's own "deps routed through github, not local fs" rule.
No feedback channel. The recipe prints a header ("[QC] Running structured text formatting") but emits nothing after the mutation telling the agent which files changed, why, or what to do next. From the agent's perspective the gate just succeeded and left unnamed foreign edits in the tree — exactly the precondition for the AGENTS.md "uncommitted changes you did not personally create = user work" rule that triggers refusal.
So both of your hypotheses are correct: the changes are silently produced and aggregation-style cleanup that ought to be committable in one stroke. Two paths, with a recommendation to combine them.
Path A — Make the cleanup auto-committable
Three sub-options, gated by hook timing:
Fail-loud --check in the hook + dedicated just format-fix recipe. Swap ruff format → ruff format --check, ruff check --fix → ruff check (no --fix in the gate), prettier --write → --check. Hook exits non-zero with a banner:
[QC] Formatter would rewrite N files. Re-run with the fixer, commit the cleanup separately, then retry:
    just format-fix
    git add -A && git commit -m "style: apply QC autoformat"
Formatter is positive-gradient cleanup (whitespace / import order / safe autofixes). Safe to commit as a separate sweep.
This is the most aligned with the repo's own "fail loudly, no fallbacks, no silent side-effects" ethos. Agent action is explicit and one-shot. Cost: two commits per cycle when formatting is needed (acceptable; it's already the standard pattern in most Python repos using the pre-commit framework — and agents are well-trained on this pattern).
Auto-stage formatter output into the in-flight commit (pre-commit). After the mutating formatter runs, git add only the formatter-touched file set — git status --porcelain before vs after the run, diff, add only that set — then let the commit finalize. Pros: zero extra commits, no phantom-commit confusion, formatter output rides the agent's logical change (whitespace riding with logic is unremarkable — every committed Python repo does this). Cons: mutates the agent's snapshot mid-commit; should require git status after git add -u excludes file paths the agent staged for semantic reasons vs the formatter staging only the formatter-touched files. This is the pre-commit framework's default behavior and the most common pattern globally.
Auto-create a separate cleanup commit in pre-push. Run formatter, git add only the formatter-changed files, git commit -m "style: apply QC autoformat (positive-gradient sweep) [skip ci]" on top of the branch, exit 0 so push proceeds. Caveats: pre-push runs after the commit already exists; the new commit lands on the branch tip and is included in the push only if the hook returns before the upload starts (git re-reads the ref after the hook exits — it does pick up commits added during pre-push, but I'd verify with a fixture once). The agent then sees a phantom "style:" commit it did not author — mitigated by an explicit banner ("A separate positive-gradient cleanup commit was added on top of your branch and will be pushed alongside your work; do not amend it away"). This is the literal answer to your "bundled into their own commits automatically" question, and works when the cleanup is uniformly non-semantic (true for ruff format, prettier --write, semgrep --autofix on safe rules). Do not use this path if any autofix rule has semantic scope.
Path B — Inject agent-parseable feedback
Required regardless of Path A choice, because even auto-bundling fails if the agent decides before the hook fires that the worktree is dirty with foreign work (e.g., it runs git status first, sees the previous commit's leftover formatter output, and halts). The feedback must:
Be a labeled, structured block in the hook's stdout/stderr so an agent can match the wording — the agents currently fail purely on absence of a distinguishable signal:
[QC-FORMATTER] Positive-gradient cleanup applied to N files in the caller repository.
Changes are intentional, non-semantic, safe to commit.
Files (caller-repo only, no submodule): <list>
Next steps:
  1. just format-fix  (if you want a manual sweep instead)
  2. git add -A
  3. git commit -m "style: apply QC autoformat (positive-gradient sweep)"
  4. retry your push/commit
Do NOT discard these changes and do NOT treat them as foreign work — they were emitted by this hook.
Appear both when the formatter runs (so the agent can act immediately) and after it ran (in case the agent comes back later, finds the dirty tree, and needs to identify the provenance). The cheapest way: the hook writes a .agents/format-sweep.log with timestamp + file list + the same instructions, and the banner points to it. Agents reading the worktree later can cat it and stop misattributing.
Boundary fix (independent of either path)
The formatter must not enter the submodule. Mechanism:
qc-excludes.toml already drives exclusions (per _format-structured-text: it errors on empty excludes). Add the submodule path (and any git submodule paths) to the exclude list.
For ruff/prettier/flowmark, also pass explicit --exclude / path filters keyed off git submodule status --recursive so the formatter is constrained even when excludes go stale.
Add a self-test: assert git diff --submodule=diff --name-only outside the caller repo is empty after a _normalize-common run; fail loud if not. This is the kind of boundary leak the repo's Policy Alignment Gate is built to prevent, and it should be locked with a // ruleid:-style fixture exactly as the Tier 1 gate requires.
Recommendation
Combine:
Path A option 1 (fail-loud --check + dedicated just format-fix) as the default — it matches the repo's existing fail-loud doctrine, is the pattern agents are best-trained on, and avoids making phantom commits the agent has to reinterpret.
Path B (labelled, structured banner + persistent .agents/format-sweep.log provenance trail) as the universal complement, so even an agent that arrives after the sweep can recognize the edits as QC-made.
Auto-bundle (Path A option 3) as opt-in, gated behind a flag, only for repos where the formatter is provably non-semantic and the project owner wants zero-friction hygiene. Keep the default fail-loud so the agent always knows what it's being told to commit.
Submodule exclusion + ruleid fixture as an orthogonal bug fix that must land regardless.
This converts the silent-mutation anti-pattern (the exact thing the repo's own infrastructure rules forbid) into a named, fail-loud, agent-actionable signal, and gives the formatter a literal provenance log so the "is this foreign work?" decision stops being the failure mode.
Turn Summary:
Completed: Inspected the QC formatter/hook wiring in ~/ai-review-ci and produced a remediation design for the silent-autoformatter-confuses-agents failure mode.
Validated by: Direct read of justfiles/python.just (lines 244–268, 663–674) and justfiles/shared.just (lines 24–106) confirming that _normalize / _normalize-common call ruff check --fix, ruff format, prettier --write, and semgrep --autofix — all mutating, none --check — wired into both test (pre-commit) and test-ci (pre-push). The agent's quote ("Sage preflight passed, formatter rewrote files including the submodule") matches exactly.
Failures: None.
Decisions:
Chose fail-loud --check + dedicated format-fix as the recommended default over silent auto-commit, on the grounds that it matches the repo's existing "fail loudly, no silent side-effects" doctrine and is the pattern agents are best-trained on.
Recommended a labelled, structured hook banner plus a persistent .agents/format-sweep.log provenance trail as the feedback channel, because the failure mode is判 misattribution-of-provenance, not mechanics.
Recommended auto-bundle-on-push as opt-in only, gated behind a provably-non-semantic guarantee.
Flagged the submodule touch as an independent boundary bug requiring its own ruleid fixture per Tier 1 of the Policy Alignment Gate, separate from the UX remediation.
Outstanding Tasks (if you want me to implement any of these):
Convert _normalize / _normalize-common to fail-loud --check semantics and add format-fix recipes in python.just / shared.just / bun.just / rust.just.
Add the labelled banner + .agents/format-sweep.log writer to the normalizer recipes.
Add submodule paths to qc-excludes.toml, add explicit git submodule status-driven path filters to each formatter call, and add a self-test fixture asserting no formatter changes outside the caller repo.
Open a work-unit issue (per the repo's issue-first PR lifecycle) capturing the problem statement, acceptance criteria, and proof obligations, before broad implementation.
Verify pre-push commit-add timing with a fixture once if auto-bundle-on-push is selected.
▣  Interactive · GLM-5.2 · 6m 34s
....1 is wrong, this gives agents the choice NOT to format. Obviously wrong. And you seem extremely confused. The formatters are all plainly listed here. No autoformatter changes semantics....it's **formatting**..... so A3 is almost obviously correct
....1 is wrong, this gives agents the choice NOT to format. Obviously wrong. And you seem extremely confused. The formatters are all plainly listed here. No autoformatter changes semantics....it's **formatting**..... so A3 is almost obviously correct
Bad Request: {"status":400,"title":"Bad Request","detail":"Function id '87ea0ddc-cff1-4bca-bf8b-3bd98a35ddd0': DEGRADED function cannot be invoked"}
▣  Interactive · minimax-m3
