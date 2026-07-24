---
name: label-routing
description: Use before opening or triaging a GitHub issue or PR on any repo managed by ai-review-ci — routes each issue to the correct canonical label (type / scope / status / area / complexity) and explains the issue-lifecycle labels (epic, work-unit, research, split-from-*, superseded) and the complexity axis (drift risk, for agent-dispatch tiering).
---

# Label Routing

The canonical label taxonomy is owned by `ai-review-ci` and defined in one place: `src/ai_review_ci/data/labels.json`. Every managed repo should carry this set.
To propagate it to a repo:

```bash
just -f ~/ai-review-ci/justfile install-labels owner/repo
# or:  uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci install-labels --repo owner/repo
```

`install-labels` reconciles the **mandatory** canonical set *exactly*: it creates missing canonical labels and updates any whose color/description drifted, and leaves a repo's own extra labels untouched.
The canonical set is not optional, and it is matched by **exact name** — a close-but-unequal variant (e.g. `Bug` vs `bug`) is a *misalignment* with global QC, not a match.
Exact names are what let a canonical label such as `bug` mean the same thing in every repo and aggregate cleanly across them.
Extra, repo-specific labels are allowed (we cannot predict every repo's needs); the canonical ones are required.

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

`help wanted`, `good first issue`, `wontfix`, `duplicate`, `invalid`, `question` — note the spaces in the first two; do not create hyphenated variants.

## `area:*` labels — ownership

`area:*` maps an issue to the surface that owns it.
The taxonomy ships a common pool (`area:frontend`, `area:backend`, `area:ci`, `area:deps`, `area:docs`); a repo may add its own `area:*` labels for its specific surfaces (as `ai-review-ci` itself does with `area:policy-index`, `area:qc-rules`, etc.). Repo-specific area labels are NOT part of the canonical taxonomy and are not pushed to other repos.

## `complexity:*` labels — drift risk, for dispatch tiering

| Label | Meaning |
| --- | --- |
| `complexity:low` | Concrete, checkable, composes existing work; mistakes fail fast. |
| `complexity:medium` | Real modeling/theorem judgment, partial existing support, some weakly-guarded surface. |
| `complexity:high` | Establishes downstream work, weakly guarded by QC, high reinvention potential; small errors compound. |

**Complexity is drift risk, not size.** It does *not* measure lines of code, effort, or
mathematical/technical sophistication. It measures where a wrong or hollow artifact is most
dangerous — rate a work unit *higher* the more of these hold:

- it **establishes downstream work** (many units consume its definitions/interfaces), so an early mistake compounds;
- it is **prone to silent drift** — the intended meaning can decay without any single visible break;
- it is **weakly guarded by standard QC** — a plausible-but-wrong version still **builds, lints, passes hooks and tests**;
- it invites **reinvention/novelty** instead of **composing known constructions** (Mathlib, the DeepMind/formal-conjectures corpus, the rest of the repo).

### The inversion this label captures

Difficulty and complexity are *different axes*. A unit can be mathematically deep yet **low**
complexity: implementing a Grothendieck construction / fibred category is sophisticated, but it
leans on existing Mathlib APIs, and even a from-scratch attempt that *confabulates* the
construction simply won't have the required universal property — that failure surfaces loudly the
moment downstream work expects the property. Conversely, a small **model-independent interface**
can be **high**: a fake classifier whose comparison 2-cell is `Nonempty (CatCommSq …)`, a registry
row whose `eval(e) ≃ C` witness is stubbed, a deep theorem laundered as a bare `Prop`/axiom, or a
resolver that returns a *membership path* instead of a *lift into a structure fiber* — each of these
**compiles, lints, and passes CI while being semantically empty**. That is precisely the threat the
`complexity:high` label flags: the standard gates will report green, so verification cannot rely on
them.

### How the tier drives dispatch

- **`complexity:high`** — assign the highest-capability agent; **review the semantic core by hand
  (green CI is not evidence)**; require an audit of existing libraries *before* new abstractions;
  do **not** run independent agents concurrently across high units that share definitions (they
  drift apart at the seams).
- **`complexity:medium`** — capable agent, normal review focused on the one weakly-guarded surface
  named in the issue.
- **`complexity:low`** — standard agent; CI-guarded; safe to parallelize.

Apply exactly one `complexity:*` to every `work-unit`. Group/`epic` issues carry none (complexity
lives on the leaf that a branch claims). Re-rate a unit if its dependency reach or the availability
of a reusable construction changes.

## Routing checklist when opening an issue

1. Exactly one `type` label (`bug` only for observed defects).
2. A `scope` label when the issue is an epic, a claimable work-unit, or research-gated.
3. Exactly one `complexity:*` label on every `work-unit` (drift risk, not size).
4. An `area:*` label naming the owning surface, when one applies.
5. `blocker` only when it actually blocks other tracked work.

To change the taxonomy itself, edit `src/ai_review_ci/data/labels.json` in this repo — never redefine labels per-repo.
See `git-guidelines` for the issue-filing workflow.
