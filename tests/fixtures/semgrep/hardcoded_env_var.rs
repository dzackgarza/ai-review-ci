// POLICY.NO_HIDDEN_CONFIG: an environment variable set to a value written in
// the source. A value that the program computes is not hidden configuration.
use std::env;

fn configure(directory: &str) {
    // ruleid: rust-no-hardcoded-env-var
    env::set_var("NODE_ENV", "production");
    // ruleid: rust-no-hardcoded-env-var
    std::env::set_var("API_HOST", "api.example.org");

    // ok: rust-no-hardcoded-env-var
    env::set_var("PATH", directory);
    // ok: rust-no-hardcoded-env-var
    std::env::set_var("PATH", format!("{}:{}", directory, env::var("PATH").unwrap()));
}
