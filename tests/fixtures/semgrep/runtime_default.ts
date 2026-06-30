// Fixtures for POLICY.RUNTIME_DEFAULT precision (#120).
//
// `ruleid:` lines are fail-soft DEFAULTS — a missing/malformed value silently
// backfilled with a non-empty success-shaped stub. These are the real target of
// the policy and MUST flag. `ok:` lines use `||`/`??` as a boolean connective
// (guard, JSX boolean prop, search predicate) or normalize genuinely-optional
// owned-boundary values to empty literals; those MUST NOT flag. Position and
// fallback shape, not the bare operator, are the signal.

export function fallbacks(headers: Headers, prDetail: any, comment: any, run: any, repo: any) {
  // ruleid: no-nullish-coalescing
  const title = repo.title ?? "Untitled repository";
  // ruleid: ts-no-or-default
  const ciStatus = prDetail?.ci_status || { state: "pending", runs: [] };
  // ruleid: no-nullish-coalescing
  const avatar = { avatar_url: comment.author.avatar_url ?? "about:blank" };
  // ruleid: ts-no-or-default
  const tags = repo.tags || ["uncategorized"];
  // ruleid: ts-no-or-default
  const logs = run.logs || "[INFO] Run build initialized correctly.";
  // ruleid: no-nullish-coalescing
  const retries = repo.retries ?? 0;
  return { title, ciStatus, avatar, tags, logs, retries };
}

export function boundaryNormalization(optionalFilters: string[] | undefined, scaffold: { fields?: Record<string, unknown> }, mount: Element, dep: { key?: string }) {
  // ok: no-nullish-coalescing
  const filters = optionalFilters ?? [];
  // ok: no-nullish-coalescing
  const fields = scaffold.fields ?? {};
  // ok: no-nullish-coalescing
  const label = mount.getAttribute("data-label") ?? "";
  // ok: ts-no-or-default
  const sortKey = dep.key || "";
  return { filters, fields, label, sortKey };
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
