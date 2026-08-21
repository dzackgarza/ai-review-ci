# Contributing

Read this before filing an issue or opening a pull request here.

Most proposals that reach this repository are well-reasoned, technically competent, and
wrong for it. They assume a model of quality control that this repository rejects, and
nothing else here states that model plainly enough to catch them. So they arrive, they
look like ordinary work, and they get built.

## The stances, plainly

- **QC is not opt-in.** Opting out is a QC failure, not a configuration.
- **QC is not optional.** A repository does not choose which gates apply to it.
- **Overriding QC fails QC.** An override is not a resolution of a finding. It is the
  finding.
- **Local overrides are banned.** There is no repo-writable surface that silences,
  relaxes, downgrades, or skips a rule.
- **There is no such thing as an override that is correct for one repository and not
  another.** A rule is either right for all repositories or wrong for all of them.
- **The onus is on the non-conforming repository.** When a repository and a rule
  disagree, the default resolution is that the repository adopts the intended
  architecture.

You may argue that a global rule is wrong. That argument is made **globally**, about the
rule, for every repository at once. "This rule is wrong here" is not a smaller version of
that argument. It is a different claim, and this repository does not accept it.

## Uniformity is the product

The purpose of global QC is to make repositories converge on one architecture. It is not
to accommodate whatever architecture each repository already has.

Sprawl is the failure being prevented. A fleet where every repository has its own shape,
its own exceptions, and its own bespoke QC is leaky and cannot be audited: no one can say
what is enforced anywhere without reading every repository. Every accommodation moves the
fleet toward that state, and each one looks locally reasonable while doing it.

So a rule that fires on correct code is a **defect in the rule**, and the repair happens
here, in the rule, for everyone. That is the only repair shape there is.

## Where the rules come from

The rules are not defaults, and they are not best practice as generally understood. They
are highly opinionated house style, written **in response to observed failures** — years
of watching agent-produced code fail in specific, repeated ways. Each rule is a
countermeasure to something that actually happened.

That history is not visible from inside a single repository hitting a single wall. When
you encounter a rule that seems too strong, you are almost certainly missing the incident
that produced it. Take your own judgment about the rule with a grain of salt accordingly:
the rule has evidence behind it that you do not have.

This is also why a rule looking unusual is not an argument against it. Many of them are
deliberately far from what training data would suggest, because what training data suggests
is what the rule exists to stop.

## What QC is for

QC exists to stop agents in their tracks.

Not to advise. Not to score. To halt work at a bad pattern or a bad architectural
decision, and redirect the agent into reading about the correct architecture — which is
typically **a rewrite that obviates the problem entirely**.

The predictable response is the one to watch for in yourself. Faced with a gate, agents
overwhelmingly do not perform the rewrite. They construct increasingly elaborate ways to
preserve the existing architecture and route around the gate: a narrower carve-out, a
declaration the rule would recognize, a mode, a threshold, a place to record that this
case is different. Each iteration is more complex than the rewrite would have been. That
escalation is the signal that the rewrite is the actual work.

Agents treat QC as something to golf. It is not a score to optimize. A gate that a repository
can bring to green by adjusting the gate has stopped being quality control.

## The asymmetry: strictifying versus relaxing

This is the operative rule for proposals about rules themselves.

**Making a rule stricter is almost always allowed**, provided there is a clear
architectural remediation that obviates the flagged pattern. Propose these freely; they
are ordinary work.

The worked example is error handling. The house style removes it, and forces enumeration
of cases with explicit handling of every known error instead. That is much harder work. It
is markedly absent from average training data. It produces significantly better code.
Agents fight it, because roughly 95% of the code they have seen uses error handling, so
they conclude they understand the problem landscape better than the rule does — without
knowing the years of house style behind the ban. The predictable output is a request for
an exception, a relaxation, or an argument that the rule is too strong.

**Anything other than strictifying requires detailed human interactive work.** Relaxing a
rule, narrowing it, downgrading its severity, adding a condition under which it does not
fire, or introducing a mechanism that makes it stand down — none of these are agent-owned
changes. They do not happen because an issue argued for them well.

You may report the problem. Report it in as much detail as you like. **A report is not a
decision**, and no amount of argument in an issue body converts one into the other.

## Arguments carry no weight by default

This repository takes a deliberate stance against agent assertions that an override or a
relaxation is *correct*. Such an assertion is never accepted at face value, and its
persuasiveness is not evidence.

The reason is empirical and well documented here: agents hold strong priors that are the
polar opposite of this repository's stance, and will argue at length to move QC toward
those priors rather than realign themselves to comply. A long, careful, internally
consistent argument for a relaxation is the expected output of that prior, not a signal
that this case is the exception.

So the burden is asymmetric on purpose. Strictification is cheap because its failure mode
is more work. Relaxation is expensive because its failure mode is a fleet that no longer
means anything.

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

If the answer is "only this repository, by changing the rule for everyone," the proposal
fits.

Both halves are recorded as enforceable policy — `POLICY.GLOBAL_QC_AUTHORITY` and
`POLICY.NO_QC_SILENCING` in `skills/policy-index/references/policies.md`.

### Sanctioned exceptions exist, and this is their shape

The worked example is the issue-linked `xfail`: a red proof test may carry
`@pytest.mark.xfail(reason="... #N", strict=True)` while issue N is open, and the gate
rejects the marker once N closes.

Note every property. The owner granted it interactively. The runner enforces it. The
citation is checkable. It expires on its own. A repository cannot grant itself one, and
cannot keep one alive by declining to update its own config. Anything proposed as an
exception that lacks these properties is not one.

## Three ways the inversion gets in

Every specimen below is a real open issue in this repository. None is careless work. That
is the point: this is what the failure looks like when everyone involved is conscientious.

### 1. It arrives with a rationale for why it is compliant

The strongest form cites the governing policy, acknowledges it, and explains why this
particular mechanism satisfies it anyway. From #254, now absorbed into #269:

> The sage/python QC tier in this repo's justfiles can run a private-usage siting check
> when the target repo carries a `pyrightconfig.json` declaring it (**presence of the
> config is the opt-in**; the gate then must pass). Per the no-repo-writable-suppression
> policy, exclusions live in the target repo's committed config, visible in review — but
> the RUNNER is owned here, so a target repo cannot un-wire the check while keeping the
> config.

Careful reasoning, backwards conclusion. A repository that deletes the file is not running
the gate. Whether the gate runs at all is the switch, and the repository holds it.
"Visible in review" is not the standard. "The repository cannot turn it off" is.

#363 is the same move at rule level. It correctly rejects a suppression comment as banned,
correctly rejects renaming the constant as honest-label laundering, then proposes "an
explicit invariant-declaration convention the rule recognizes" — a downstream declaration
that makes the rule stand down at a site. The same thing as the two mechanisms it just
rejected, with a better name.

### 2. It arrives as one option on a menu

The most common shape, and the most dangerous, because the issue reads as reasonable as a
whole. Two or three directions are listed, one of which is the inversion, presented as
coequal:

- **#301**: "Decide whether the loopback signal is derived structurally (bind site in the
  same module or class) **or declared by the consuming repo**."
- **#379**: "make the diff gate the only mode so local and CI agree; or keep the whole-repo
  scan as a non-blocking report locally; **or give the ceiling a declared-exemption surface
  for shapes like dispatch switches**."
- **#367**: the gate should distinguish an unavailable environment from bad content —
  correct — "or **has a sanctioned non-red bypass**" — not correct.

An implementing agent reads a menu and picks one. Nothing marks the poisoned option. So:
**when a proposal offers alternatives, every alternative must pass the authority test.**
One that does not is not a lesser choice to weigh; it is a defect in the issue, and the
issue gets corrected before implementation rather than routed around.

### 3. It arrives absorbed into legitimate work

#269 is a sound work unit. It has absorbed six other issues verbatim, and #254 is one of
them. A misaligned ask inside an aligned work unit inherits that work unit's legitimacy,
and whoever implements #269 will implement #254 as part of it without ever evaluating it
separately.

Absorbing issues is fine. Absorbing them **verbatim and unexamined** is how a proposal
skips the only review it was going to get. Re-derive each absorbed ask against the
authority test at absorption time.

## Arguments that are not evidence

These recur, they are persuasive, and none is sufficient:

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
- *The rule is unusual / no one else does this.* Correct, and deliberate. See **Where the
  rules come from**.
- *Refactoring to satisfy the rule is disproportionate work.* The rewrite is frequently the
  point of the rule.

## The opposite failure

Over-reach is real and this repository has shipped it. A reviewer, gate, or scan producing
findings nobody asked for costs more than it catches.

Every finding a reviewer emits must trace to one of three sources:

1. the original task the work claimed to complete,
2. a recorded repository policy,
3. a regression the change introduced.

A technically true observation with no such source is a product suggestion and must not
enter remediation. #362 records a bounded owner-local change becoming 38 accepted new
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
someone who has more context than you and will not use it. #298 records this pattern and
the issues it produced.

A good issue carries:

- the observable symptom, with the command or output that shows it;
- the evidence that locates it — file and line, or the run that failed;
- what breaks because of it.

If you have a hypothesis about the cause, label it a hypothesis. If you are proposing a
direction, say so, and expect it to be re-derived rather than implemented. If you offer
more than one direction, check each against the authority test before writing it down.

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
