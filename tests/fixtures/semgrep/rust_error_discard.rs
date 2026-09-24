// Fixture for rs-no-result-ok, rs-no-unwrap-or and rs-no-unwrap-or-default. The call is the
// signal; words that merely contain "ok" or "unwrap_or" must not fire.

// ok: rs-no-result-ok
use tokio::sync::Mutex;

fn discards(parsed: Result<u16, std::num::ParseIntError>, port: Option<u16>) {
    // ruleid: rs-no-result-ok
    let dropped = parsed.ok();
    // ruleid: rs-no-unwrap-or
    let defaulted = port.unwrap_or(8080);
    // ruleid: rs-no-unwrap-or-default
    let zeroed = port.unwrap_or_default();
}

async fn keeps(state: &Mutex<Vec<String>>, book: &str) -> Result<(), std::io::Error> {
    // ok: rs-no-result-ok
    let guard = state.lock().await;
    // ok: rs-no-result-ok
    let looked_up = guard.iter().find(|entry| entry.as_str() == book);
    // ok: rs-no-unwrap-or
    let computed = looked_up.map(String::len).unwrap_or_else(|| book.len());
    // ok: rs-no-result-ok
    Ok(())
}
