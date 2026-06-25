// Fixtures for POLICY.NO_TYPE_ESCAPE / no-double-cast (#46).
//
// Decision: there is NO sanctioned double-cast form. A justification comment
// must not create an escape hatch — a reason can be confabulated, and QC must
// not be in the business of adjudicating reasons. Every double cast is blocked
// and routed to REMEDIATE.STRUCTURED_TYPES (fix the type at the boundary).
// Single casts are a different concern and this rule does not fire on them.

export function erasures(blob: unknown, x: unknown, y: unknown) {
  // ruleid: no-double-cast
  const a = blob as unknown as Blob;
  // ruleid: no-double-cast
  const b = x as any as string;
  // A plausible-looking justification does NOT admit the cast:
  // ruleid: no-double-cast
  const c = y as unknown as Foo; // boundary: API accepts Blob at runtime
  // Parentheses do not bypass the rule either:
  // ruleid: no-double-cast
  const d = (x as unknown) as Bar;
  return { a, b, c, d };
}

export function singleCasts(x: unknown) {
  // ok: no-double-cast
  const e = x as string;
  // ok: no-double-cast
  const g = JSON.parse("{}") as Record<string, unknown>;
  return { e, g };
}
