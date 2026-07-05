// Additional POLICY.RUNTIME_DEFAULT regression fixtures for PR #149.
// These lock the remaining #120/#130 boundary: literal value fallbacks still flag,
// while non-literal boolean/control expressions stay clean.

export function literalFallbacks(repo: any) {
  // ruleid: no-nullish-coalescing
  const owner = repo.owner ?? null;
  // ruleid: no-nullish-coalescing
  const enabled = repo.enabled ?? true;
  // ruleid: no-nullish-coalescing
  const archived = repo.archived ?? false;
  // ruleid: no-nullish-coalescing
  const summary = repo.summary ?? repo.description ?? "";
  // ruleid: ts-no-or-default
  const label = repo.label || "";
  return { owner, enabled, archived, summary, label };
}

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
