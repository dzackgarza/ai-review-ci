// Fixtures for POLICY.RUNTIME_DEFAULT precision (#120).
//
// `ruleid:` lines are fail-soft DEFAULTS — a missing/malformed value silently
// backfilled with a literal stub. These are the real target of the policy and
// MUST flag. `ok:` lines use `||`/`??` as a boolean connective (guard, JSX
// boolean prop, search predicate); there is no default value operand, so they
// MUST NOT flag. Position, not the bare operator, is the signal.

export function fallbacks(headers: Headers, prDetail: any, comment: any, run: any, repo: any) {
  // ruleid: no-nullish-coalescing
  const etag = headers.get("etag") ?? "";
  // ruleid: ts-no-or-default
  const ciStatus = prDetail?.ci_status || { state: "pending", runs: [] };
  // ruleid: no-nullish-coalescing
  const avatar = { avatar_url: comment.author.avatar_url ?? "" };
  // ruleid: ts-no-or-default
  const tags = repo.tags || [];
  // ruleid: ts-no-or-default
  const logs = run.logs || "[INFO] Run build initialized correctly.";
  // ruleid: no-nullish-coalescing
  const retries = repo.retries ?? 0;
  return { etag, ciStatus, avatar, tags, logs, retries };
}

export function guards(res: any, body: string, e: KeyboardEvent, dependabot: any, codeScanning: any, secretScanning: any) {
  // ok: ts-no-or-default
  if (res.status !== 200 || !res.data) return;
  // ok: ts-no-or-default
  if (res.status === 403 || res.status === 404) return;
  // ok: ts-no-or-default
  if (dependabot === undefined || codeScanning === undefined || secretScanning === undefined) return;
  // ok: ts-no-or-default
  if ((e.ctrlKey || e.metaKey) && e.key === "p") return;
}

// ok: ts-no-or-default
export const disabled = (posting: boolean, body: string) => posting || !body.trim();
// ok: ts-no-or-default
export const pred = (c: any, q: string) => c.title.includes(q) || c.subtitle.includes(q) || c.category.includes(q);
