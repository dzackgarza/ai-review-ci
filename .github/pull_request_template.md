## Summary

<!-- What this PR does, and the issue(s) it closes / references. -->

## Policy alignment gate — required

Authoritative policy is vendored in-repo: `reviews/vendor/policy-index/SKILL.md` +
`references/policies.md`. Load it **from this checkout** — do not rely on globally-installed
skills (remote agents do not have them). Full rationale: AGENTS.md → **Policy Alignment Gate**
and the wiki [Policy Alignment Gate](https://github.com/dzackgarza/ai-review-ci/wiki/Policy-Alignment-Gate).

### Tier 0 — every PR

- [ ] Loaded the vendored `POLICY.*` records. Codes this change touches or risks: `POLICY.____`
- [ ] No **Invalid local fix** introduced — no new fallback, runtime default, optional
      core-state, swallowed error, or partial-success path that makes required work look
      successful after it should fail loudly.
- [ ] No empty/falsy-literal fallback (`""`, `[]`, `{}`, `null`, `false`, `0`) added or
      reclassified as "safe." Optional state is an explicit typed state at the boundary.

### Tier 1 — only if this PR touches `tool-configs/`, `reviews/`, detectors, or QC `justfiles/`

- [ ] **Regression-lock:** a `ruleid` (or equivalent) fixture proves each previously-flagged
      banned pattern **still fires**. Precision narrows by *position*, never by *value*.
- [ ] This change weakens no `POLICY.*` and converts no true finding into scanner silence.
- [ ] Any policy-*semantics* change was authored upstream in `dzackgarza/ai` and re-vendored
      via `just sync-policy-index` — not edited locally (the vendor is hash-pinned).

## Evidence

<!-- Commands, fixtures, and test output proving the boxes above. Not assertions — artifacts. -->
