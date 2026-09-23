// Direct console.error bypasses the durable application error boundary.

export function bad(err: unknown, logger: { error: (...args: unknown[]) => void }) {
  // ruleid: ts-no-console-error
  console.error(err);
  // ruleid: ts-no-console-error
  console.error("operation failed", err);

  // ok: ts-no-console-error
  reportError(err);
  // ok: ts-no-console-error
  logger.error("operation failed", err);
}

declare function reportError(...args: unknown[]): void;
