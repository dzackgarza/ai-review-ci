// Additional JSX POLICY.RUNTIME_DEFAULT regression fixtures for PR #149.
// These prove that rendered literal fallbacks still flag, but boolean JSX props
// with non-literal operands stay clean.

export function BoundaryCard({ content, title, hiddenReason, repo, posting, body }: any) {
  return (
    <section>
      {
        // ruleid: ts-no-or-default
        content || ""
      }
      {
        // ruleid: no-nullish-coalescing
        title ?? null
      }
      {
        // ruleid: no-nullish-coalescing
        hiddenReason ?? false
      }
      <button
        disabled={
          // ok: ts-no-or-default
          posting || !body.trim()
        }
      >
        Submit
      </button>
      <div
        aria-hidden={
          // ok: ts-no-or-default
          repo.archived || repo.private
        }
      />
    </section>
  );
}
