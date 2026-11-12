// POLICY.NO_HIDDEN_CONFIG: an environment variable set to a value written in
// the source. A value that the program computes is not hidden configuration.

declare const directory: string;
declare const pathOfTheRun: string;
declare function shellPath(): Promise<string>;

export async function configure(): Promise<void> {
  // ruleid: ts-no-hardcoded-env-var
  process.env.NODE_ENV = "production";
  // ruleid: ts-no-hardcoded-env-var
  process.env["API_HOST"] = 'api.example.org';
  // ruleid: ts-no-hardcoded-env-var
  process.env.LANG = `C.UTF-8`;

  // ok: ts-no-hardcoded-env-var
  process.env.PATH = `${directory}:${pathOfTheRun}`;
  // ok: ts-no-hardcoded-env-var
  process.env.PATH = pathOfTheRun;
  // ok: ts-no-hardcoded-env-var
  process.env.PATH = await shellPath();
}
