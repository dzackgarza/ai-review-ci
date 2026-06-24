## Intended Result

Harden reviewer signal quality so ai-review-ci emits slop/policy findings that match the bridge-burning threat model, rejects generic bug/perf churn, and proves classifier quality with reusable fixtures.

The reviewer should help agents find validation evasion, fallback/default behavior, weak proof, and policy-misaligned remediation pressure without turning review into generic style or speculative performance critique.

## Scope

Included:

- Build an empirical eval corpus from accepted/rejected PR #7 review cases.
- Re-anchor reviewer output on anti-slop/policy findings instead of generic bugs or micro-perf.
- Prevent reviewer-authored remediation suggestions that violate project policy.
- Clarify optional/absent-data handling as reviewer-facing doctrine, linked to policy-index optionality work.
- Add reusable slop/clean fixture coverage for true positives, true negatives, false positives, and false negatives.

Excluded:

- Review-delivery transport, deduplication, or status-state work owned by #42.
- Policy-index doctrine edits owned by #58 except where reviewer consumption requires a reference.
- One-off prompt tweaks without an eval witness.

Preserved behavior:

- Review findings remain diagnosis-first and must cite concrete evidence.
- Remediation guidance remains canonical and policy-owned, not invented by reviewer output.

## GitHub Tracking

- Milestone: [Reviewer signal quality](https://github.com/dzackgarza/ai-review-ci/milestone/2)
- Development links:
  - Closes #41
  - Closes #19
  - Closes #20
  - Closes #21
  - Closes #28
  - Closes #62
  - Refs #58

## Execution Structure

#28 creates the empirical target. #19 and #20 change reviewer classification and output constraints. #21 applies optionality doctrine once #58 is sufficiently defined. #62 turns the resulting threat model into reusable fixtures. #41 closes only when these workstreams are integrated and evidenced.

## Milestone Tree

- [ ] **M1 - Reviewer signal quality and policy alignment** ([#41](https://github.com/dzackgarza/ai-review-ci/issues/41))
  - Complete when: reviewer output is measurably anchored to slop/policy findings, avoids policy-misaligned remediation, and is covered by reusable evaluation fixtures.

- [ ] **F1 - Empirical slop/generic eval corpus** ([#28](https://github.com/dzackgarza/ai-review-ci/issues/28))
  - Behavior: extract labeled cases from PR #7 into a corpus with expected slop, generic, policy-misaligned, and clean classifications.
  - Acceptance: each case records source evidence, expected label, and why the label is policy-relevant.
  - Evidence: pending corpus commit and fixture/eval command output.

- [ ] **W1 - Threat-model aligned findings** ([#19](https://github.com/dzackgarza/ai-review-ci/issues/19))
  - Behavior: reviewer prompts/classifiers emit bridge-burning slop findings and reject generic bugs/perf unless tied to the threat model.
  - Acceptance: eval cases show generic bug/perf findings are suppressed or downgraded while real slop remains surfaced.
  - Evidence: pending prompt/config diffs and eval output.

- [ ] **W2 - Policy-aligned remediation firewall** ([#20](https://github.com/dzackgarza/ai-review-ci/issues/20))
  - Behavior: reviewer output cannot propose remediation that violates policy or bypasses canonical guidance.
  - Acceptance: policy-misaligned suggested fixes fail the eval or are rendered as diagnosis-only findings with canonical IDs.
  - Evidence: pending reviewer-template diffs and eval output.

- [ ] **W3 - Optionality doctrine consumption** ([#21](https://github.com/dzackgarza/ai-review-ci/issues/21), refs [#58](https://github.com/dzackgarza/ai-review-ci/issues/58))
  - Behavior: reviewer applies canonical absent-data rules instead of defending optional fields from priors.
  - Acceptance: eval cases distinguish irreducible domain absence from weakened required fields.
  - Evidence: pending policy reference and eval output.

- [ ] **I1 - Slop torture fixture suite** ([#62](https://github.com/dzackgarza/ai-review-ci/issues/62))
  - Behavior: ship reusable noncompliant and compliant fixtures for reviewer/tool validation.
  - Acceptance: fixtures exercise true positives, true negatives, false positives, and false negatives across the milestone threat model.
  - Evidence: pending fixture commit and verification recipes.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, the eval corpus and fixture recipes prove the reviewer behavior, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
