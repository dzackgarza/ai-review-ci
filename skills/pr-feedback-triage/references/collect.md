# Collect Returned PR Feedback

Role A owns collection.
Collection is read-only: do not disposition, edit, reply, or resolve while building the worklist.

## Read every live surface

Capture the current PR head SHA and all of these surfaces:

- current PR body and linked work-unit issue;
- formal reviews and review-decision state;
- inline review threads, including resolved and outdated threads;
- issue-style top-level PR comments and review summaries;
- check runs, annotations, and failed required checks;
- bot comments that update in place.

Do not infer the whole review state from inbox summaries, a single API surface, the web page's unresolved count, or the latest review only.

## Stable inline-thread state

Use the skill-shipped collector for the paginated inline-thread worklist:

```bash
python3 "$AI_SKILLS_DIR/pr-feedback-triage/scripts/triage_state.py" \
  --repo <owner/repo> --pr <number> --json
```

It paginates beyond GitHub's first 100 threads and every thread's first 100 comments, keys AI-review findings by `ai-review-fingerprint`, and otherwise hashes the complete visible finding so identity survives line shifts without collapsing distinct findings that share a title.
It stores resumable machine state under the repository's Git metadata, never in a tracked review ledger.
Use `--no-write` for a read-only one-shot result.

The collector owns inline-thread identity, not the other GitHub surfaces.
Read the remaining surfaces in the same round:

```bash
gh pr view <number> --repo <owner/repo> \
  --json headRefOid,body,closingIssuesReferences,reviewDecision,latestReviews,reviews,comments,statusCheckRollup
gh api --paginate repos/<owner>/<repo>/pulls/<number>/reviews
gh api --paginate repos/<owner>/<repo>/issues/<number>/comments
# For every closingIssuesReferences item, read the actual work-unit contract:
gh issue view <issue-number> --repo <owner/repo> \\
  --json number,title,body,comments,state,url,milestone,labels
gh pr checks <number> --repo <owner/repo>
gh api --paginate repos/<owner>/<repo>/commits/<head-sha>/check-runs
gh api --paginate repos/<owner>/<repo>/check-runs/<check-run-id>/annotations
```

Authentication and raw PR mechanics remain outside this stage.
This stage owns which feedback surfaces must be collected and how their results join the round worklist.

## Worklist fields

For every item preserve:

- surface and stable ID or URL;
- author and current head SHA;
- exact comment text;
- file and line when applicable;
- resolved, outdated, or check state;
- canonical duplicate identity when already known;
- existing canonical disposition reply, its URL, parsed verdict, completeness, and commit when state is `OPEN-PENDING`;
- linked issue or PR-contract obligation implicated by the claim.

Use `NEW`, `RE-RAISED`, `OPEN-PENDING`, and `CLOSED` only as collection state.
They are not dispositions.

## Route the collected state

- `NEW` and `RE-RAISED` go to [[pr-feedback-triage/references/disposition|B disposition]].
- `OPEN-PENDING` goes to [[pr-feedback-triage/references/resume-pending|pending-item resume]].
- `CLOSED` requires no action in the current round.

Do not redisposition a complete canonical reply merely because its inline thread still needs resolution.
Do not ignore an incomplete canonical reply merely because a disposition line already exists.

## Dispatch new and re-raised findings to B

Transmit raw review text, relevant source locations, the current PR contract, named policy surfaces, and verbatim owner statements.
Do not transmit A's verdict, leaning, hypotheses, preferred fix, paraphrased owner premise, or resolution preference.

A collection round is ready for disposition only after every surface above has been read and every linked work-unit issue body and comment carrying acceptance or proof obligations has been joined to the relevant finding.
Missing API access or an unsettled review run is an explicit open collection state, not permission to call the window clean.

## Migrate legacy feedback state

For an existing PR whose resolved threads cite only a retired top-level ledger, collect those threads as open migration work.
Post the canonical disposition and evidence on each affected thread before treating it as closed; the old ledger is context, not thread-local completion.

Existing repositories own their checked-in `.github/pull_request_template.md`, so installation intentionally does not overwrite it.
To migrate an installed template, compare it with the canonical [upstream template](https://github.com/dzackgarza/ai-review-ci/blob/main/src/ai_review_ci/templates/pull_request_template.md), replace the deprecated ledger checklist line in the repo-owned copy, and commit that explicit config change.
Do not delete the local template and rerun installation merely to bypass its overwrite guard.
