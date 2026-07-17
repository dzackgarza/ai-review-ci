// Fixtures for POLICY.NO_TYPE_ESCAPE / no-double-cast (#46).
//
// Arbitrary double casts and `as any` erasure stay blocked. A real
// runtime/type-surface mismatch must use the explicit runtimeBoundaryCast form,
// which requires both a runtime predicate and source-backed local justification.

declare function runtimeBoundaryCast<T>(
  value: unknown,
  predicate: (value: unknown) => value is T,
  reason: string,
): T;

interface Foo {
  id: string;
}

function isBlob(value: unknown): value is Blob {
  return value instanceof Blob;
}

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

export function boundaryAssertions(blob: unknown) {
  // ok: no-double-cast
  const allowed = runtimeBoundaryCast<Blob>(blob, isBlob, "issue #46: Zotero accepts Blob at runtime");
  // ruleid: no-unproven-boundary-cast
  const missingReason = runtimeBoundaryCast<Blob>(blob, isBlob, "");
  // ruleid: no-unproven-boundary-cast
  const missingPredicate = runtimeBoundaryCast<Blob>(blob, "issue #46: no runtime check");
  // ruleid: no-unproven-boundary-cast
  const localStoryOnly = runtimeBoundaryCast<Blob>(blob, isBlob, "works in local testing");
  return { allowed, missingReason, missingPredicate, localStoryOnly };
}

export function singleCasts(x: unknown) {
  // ok: no-double-cast
  const e = x as string;
  // ruleid: ts-no-any-cast
  const f = x as any;
  // ok: no-double-cast
  const g = JSON.parse("{}") as Record<string, unknown>;
  return { e, f, g };
}
