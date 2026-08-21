# Contributing

Read this before filing an issue or opening a pull request here.

Most proposals that reach this repository are well-reasoned, technically competent, and
wrong for it. They assume a model of quality control that this repository rejects, and
nothing else here states that model plainly enough to catch them. So they arrive, they
look like ordinary work, and they get built.

## What this repository is

`ai-review-ci` is the quality control system for every repository under this account. It
is not a linter you install. It is the authority that decides whether work is acceptable,
and it holds that authority centrally.

The word in the middle is **control**. Not guidance, not defaults, not a starting point
projects tune. A repository that fails a gate here is failing. It does not get to disagree
locally.

## The model you probably brought

Nearly every quality tool in wide use works like this:

- The tool ships defaults.
- Each project configures the tool for its own context.
- A rule that fires on code the project considers correct is a false positive, and the
  project declares it away — an ignore file, an inline comment, a threshold, an allowlist,
  a per-project override.
- Findings are advisory. Each project decides which to act on.

That model is coherent, and it is the industry norm. It is also the exact inverse of this
one, and it is where almost every misaligned proposal here comes from.

Under this repository's model:

- Rules are central and mandatory. Projects delegate to them; projects do not configure
  them.
- A rule that fires on correct code is a **defect in the rule**. The repair happens here,
  in the rule, for every repository at once.
- The consuming repository never holds a switch that makes a rule stand down. Not a
  comment, not a config key, not a declaration, not a threshold, not a mode, not the
  presence or absence of a file.
- Findings block. A gate that reports without blocking has already failed.

Both halves are recorded as enforceable policy — `POLICY.GLOBAL_QC_AUTHORITY` and
`POLICY.NO_QC_SILENCING` in `skills/policy-index/references/policies.md`.

Exceptions exist, and they are owner-granted and enforced here. The worked example is the
issue-linked `xfail`: a red proof test may carry `@pytest.mark.xfail(reason="... #N",
strict=True)` while issue N is open, and the gate rejects the marker once N closes. Note
the shape. The owner granted it, the runner enforces it, the citation is checkable, and it
expires on its own. A repository cannot grant itself one, and cannot keep one alive by
declining to update its own config.

## The authority test

Vocabulary will not tell you whether a proposal fits. Nobody proposing the inversion calls
it an exception. They call it precision, or a principled convention, or making the tool
usable. Several of the specimens below open by citing the policies that forbid what they
then propose. Apply this instead:

> **After this change, who can make the rule stand down?**

If the answer includes the consuming repository — through a config key, an annotation, a
declared invariant, a threshold, a mode, a naming convention, the presence of a file, or
anything else that repository authors — the proposal is the inversion. It does not matter
that the implementing code would live here. It does not matter that the mechanism has a
principled name, or that exclusions would be "visible in review."

If the answer is "only this repository, by changing the rule," the proposal fits.

## Three ways the inversion gets in

Every specimen below is a real open issue in this repository. None of them is careless
work. That is the point: this is what the failure looks like when everyone involved is
being conscientious.

### 1. It arrives with a rationale for why it is compliant

The strongest form cites the governing policy, acknowledges it, and then explains why this
particular mechanism satisfies it. From #254, now absorbed into #269:

> The sage/python QC tier in this repo's justfiles can run a private-usage siting check
> when the target repo carries a `pyrightconfig.json` declaring it (**presence of the
> config is the opt-in**; the gate then must pass). Per the no-repo-writable-suppression
> policy, exclusions live in the target repo's committed config, visible in review — but
> the RUNNER is owned here, so a target repo cannot un-wire the check while keeping the
> config.

The reasoning is careful and the conclusion is backwards. A repository that deletes the
file is not running the gate. Whether the gate runs at all is the switch, and the
repository holds it. "Visible in review" is not the standard; "the repository cannot turn
it off" is.

#363 is the same move on a rule rather than a gate. It correctly rejects a suppression
comment as banned by `POLICY.NO_QC_SILENCING`, correctly rejects renaming the constant as
honest-label laundering, and then proposes "an explicit invariant-declaration convention
the rule recognizes" — a downstream declaration that makes the rule stand down at a site.
It is the same thing as the two mechanisms it just rejected, with a better name.

### 2. It arrives as one option on a menu

This is the most common shape and the most dangerous, because the issue looks reasonable
as a whole. The proposal lists two or three directions, one of which is the inversion,
presented as coequal:

- **#301**: "Decide whether the loopback signal is derived structurally (bind site in the
  same module or class) **or declared by the consuming repo**." The first is a rule
  repair. The second hands the repository the switch. They are offered as alternatives.
- **#379**: "make the diff gate the only mode so local and CI agree; or keep the whole-repo
  scan as a non-blocking report locally; **or give the ceiling a declared-exemption surface
  for shapes like dispatch switches**." The first keeps authority here and the issue itself
  recommends it. The third does not.
- **#367**: a Sage rebuild collision makes a gate fail for environmental reasons. The ask
  is that the gate distinguish an unavailable environment from bad content — correct — "or
  **has a sanctioned non-red bypass**" — not correct.

An implementing agent reads a menu and picks one. Nothing in the issue marks the poisoned
option, and the doctrine has no way to say "option three is not an option." So: **when a
proposal offers alternatives, every alternative must pass the authority test.** One that
does not is not a lesser choice to weigh; it is a defect in the issue, and the issue gets
corrected before implementation, not routed around.

### 3. It arrives absorbed into legitimate work

#269 is a sound work unit — moving policy-bearing preflights into the typed tripwire
registry. It has absorbed six other issues verbatim, and #254 is one of them. A misaligned
ask inside an aligned work unit inherits the work unit's legitimacy, and whoever implements
#269 will implement #254 as part of it without ever evaluating it on its own.

Absorbing issues is fine. Absorbing them **verbatim** and unexamined is how a proposal
skips the only review it was ever going to get. Re-derive each absorbed ask against the
authority test at absorption time.

## Arguments that are not evidence

These recur, they are persuasive, and none of them is sufficient:

- *This blocks a downstream repository right now.* Correct, and that is the gate working.
  Urgency selects what to repair first. It never selects where the repair happens.
- *Contributors will stop running the gate.* If a gate is too noisy or mistiered, repair
  the precision or the tier. Never build the escape.
- *This repository has context the central rule cannot have.* Then the rule needs that
  context, here, for every repository that shares the situation.
- *Per-rule filtering is already an established mechanism here.* Existing upstream
  filtering is upstream. It is not precedent for a downstream switch. (#301 argues from
  exactly this precedent.)
- *The exclusion would be committed and visible in review.* Visibility is not authority.
- *It is only one small carve-out.* The carve-out is the feature being requested. Its size
  is not the objection.

## The opposite failure

Over-reach is real and this repository has shipped it. A reviewer, gate, or scan producing
findings nobody asked for costs more than it catches.

Every finding a reviewer emits must trace to one of three sources:

1. the original task the work claimed to complete,
2. a recorded repository policy,
3. a regression the change introduced.

A technically true observation with no such source is a product suggestion, and it must
not enter remediation. #362 records a bounded owner-local change becoming 38 accepted new
obligations, and the general review channel deleted because it could not, by construction,
satisfy the test.

Do not propose new unanchored scanners. A cron agent that reads a whole repository and
files what it thinks could be better is that shape whatever it scans for, and declaring in
the proposal that it is "not a general code-quality scanner" does not change what it does.
See #281.

## Filing an issue

**Report the problem. Do not prescribe the fix.**

An issue body is read by the implementing agent as a specification. Append "Options" or
"Suggested approaches" and those become the design, with your assumptions inherited by
someone who has more context than you do and will not use it. #298 records this pattern
and the issues it produced.

A good issue carries:

- the observable symptom, with the command or output that shows it;
- the evidence that locates it — file and line, or the run that failed;
- what breaks because of it.

If you have a hypothesis about the cause, label it a hypothesis. If you are proposing a
direction, say so, and expect it to be re-derived rather than implemented. If you offer
more than one direction, check each against the authority test before you write it down.

## Opening a pull request

Changes here propagate. Downstream repositories carry thin trigger workflows that clone
this repository at execution time, so a merge to `main` reaches every governed repository
on its next run with no action on their part. A merged mistake is not confined here.

Two consequences worth knowing before you write the change:

- Installed workflow files are repo-owned and are never overwritten by the installer.
  Removing something here does not remove it downstream; that migration is part of the
  change, not a follow-up.
- Required branch-protection contexts are computed here. Changing the set changes what
  every protected repository requires in order to merge.

The PR template's gates are not a formality. The policy alignment gate asks which
`POLICY.*` codes the change touches and expects a real answer.

## Where the rest lives

This document owns one thing: whether a proposal belongs here. It does not restate what
other documents own.

| Question | Owner |
| --- | --- |
| Why the QC and review system behaves as it does | [Global QC and Review Doctrine](https://github.com/dzackgarza/ai-review-ci/wiki/Global-QC-and-Review-Doctrine) (wiki) |
| The enforceable policy records | `skills/policy-index/references/policies.md` |
| Agent rules, PR lifecycle, review guidelines | `AGENTS.md` |
| What the system is and how to install it | `README.md` |
| Test and proof standards | `skills/test-guidelines/SKILL.md` |
