---
name: label-routing
description: Use before opening or triaging a GitHub issue or PR on any repo managed by ai-review-ci — routes each issue to the correct canonical label (type / scope / status / area) and explains the issue-lifecycle labels (epic, work-unit, research, split-from-*, superseded).
---

# Label Routing

The canonical label taxonomy is owned by `ai-review-ci` and defined in one place:
`src/ai_review_ci/data/labels.json`. Every managed repo should carry this set. To
propagate it to a repo:

```bash
just -f ~/ai-review-ci/justfile install-labels owner/repo
# or:  uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci install-labels --repo owner/repo
# or, at install time:  ai-review-ci install --repo owner/repo --branch main --profile <p> --with-labels
```

`install-labels` is idempotent and additive: it creates missing canonical labels and
updates drifted colors/descriptions, and never deletes a repo's own extra labels.

## Apply at least one `type` label to every issue

| Label | Use for |
| --- | --- |
| `bug` | Observed incorrect behavior, failures, regressions. File only for *observed* defects. |
| `enhancement` | New capability, feature, or improvement. (The taxonomy uses `enhancement`, not `feature`.) |
| `documentation` | Docs, READMEs, wiki, skill prose. |
| `test` | Test additions, fixes, or coverage work. |
| `refactor` | Behavior-preserving restructuring. |
| `chore` | Build, tooling, or dependency maintenance. |

## `scope` labels — issue lifecycle and shape

| Label | Meaning |
| --- | --- |
| `epic` | Parent issue grouping related implementation/research. Groups sub-issues; is not itself a unit of work. |
| `work-unit` | Defines a scoped, PR-sized unit of work. The thing a branch/PR claims. |
| `research` | Requires empirical evaluation before implementation — gates implementation until evidence exists. Do not start coding a `research` issue; produce the evidence first. |
| `blocker` | Blocks other work until resolved. |
| `split-from-audit` / `split-from-broad-issue` | Focused issue carved out of a broad audit or multi-finding ticket. |
| `superseded` | Closed because newer focused issues or PR work now carry the obligation. Pair with a comment naming the authoritative issue. |
| `merged-into-work-unit` | Absorbed into a work-unit issue; the work unit is the live tracker. |

## `status` labels (GitHub-default names, kept verbatim)

`help wanted`, `good first issue`, `wontfix`, `duplicate`, `invalid`, `question` — note
the spaces in the first two; do not create hyphenated variants.

## `area:*` labels — ownership

`area:*` maps an issue to the surface that owns it. The taxonomy ships a common pool
(`area:frontend`, `area:backend`, `area:ci`, `area:deps`, `area:docs`); a repo may add
its own `area:*` labels for its specific surfaces (as `ai-review-ci` itself does with
`area:policy-index`, `area:qc-rules`, etc.). Repo-specific area labels are NOT part of
the canonical taxonomy and are not pushed to other repos.

## Routing checklist when opening an issue

1. Exactly one `type` label (`bug` only for observed defects).
2. A `scope` label when the issue is an epic, a claimable work-unit, or research-gated.
3. An `area:*` label naming the owning surface, when one applies.
4. `blocker` only when it actually blocks other tracked work.

To change the taxonomy itself, edit `src/ai_review_ci/data/labels.json` in this repo —
never redefine labels per-repo. See `git-guidelines` for the issue-filing workflow.
