// Fixtures for POLICY.RUNTIME_DEFAULT precision (#120, #130).
//
// `ruleid:` lines are fail-soft DEFAULTS — a value backfilled with a literal stub,
// INCLUDING empty literals ("", [], {}). Empty and falsy literals are ambiguous
// fail-open containers (missing input / failed fetch / parse failure / no result),
// not valid owned-boundary normalization (#130, POLICY.FAIL_OPEN), so they MUST flag.
// `ok:` lines use `||`/`??` as a boolean connective (guard, JSX boolean prop, search
// predicate) with a non-literal operand; those MUST NOT flag. Position, not the bare
// operator, is the signal.

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
  // ruleid: no-nullish-coalescing
  const limit = repo.limit ?? 10;
  // ruleid: ts-no-or-default
  const timeout = repo.timeout || 30;
  // ruleid: no-nullish-coalescing
  const ratio = repo.ratio ?? 3.14;
  // ruleid: no-nullish-coalescing
  const owner = repo.owner ?? null;
  // ruleid: no-nullish-coalescing
  const enabled = repo.enabled ?? true;
  // ruleid: no-nullish-coalescing
  const archived = repo.archived ?? false;
  // ruleid: no-nullish-coalescing
  const summary = repo.summary ?? repo.description ?? "";
  return { title, ciStatus, avatar, tags, logs, retries, limit, timeout, ratio, owner, enabled, archived, summary };
}

export function emptyLiteralFallbacks(optionalFilters: string[] | undefined, scaffold: { fields?: Record<string, unknown> }, mount: Element, dep: { key?: string }) {
  // ruleid: no-nullish-coalescing
  const filters = optionalFilters ?? [];
  // ruleid: no-nullish-coalescing
  const fields = scaffold.fields ?? {};
  // ruleid: no-nullish-coalescing
  const label = mount.getAttribute("data-label") ?? "";
  // ruleid: ts-no-or-default
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

// ok: ts-no-or-default
export function chooseOwnedBoundaryValue(primary: string | undefined, inherited: string | undefined) {
  return primary || inherited;
}

// ok: ts-no-or-default
export function defaultParamWithNonLiteralOperands(value = maybeLocal() || maybeInherited()) {
  return value;
}

function maybeLocal(): string | undefined {
  return undefined;
}

function maybeInherited(): string {
  return "inherited";
}
