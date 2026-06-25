// JSX positions: a value-render default backfills a missing value and MUST
// flag; a boolean JSX prop is logical, not a default, and MUST NOT flag.
export function Card({ content, posting, body, repo }: any) {
  return (
    <div>
      {
        // ruleid: ts-no-or-default
        content || "*No description*"
      }
      <button
        disabled={
          // ok: ts-no-or-default
          posting || !body.trim()
        }
      >
        x
      </button>
      <input
        aria-hidden={
          // ok: ts-no-or-default
          repo.a || repo.b
        }
      />
    </div>
  );
}
