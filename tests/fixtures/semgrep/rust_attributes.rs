// Fixture for rs-no-allow-attr and rs-no-serde-default (ai-review-ci#420).
// Items without the banned attributes must not fire, whatever their shape.

// ruleid: rs-no-allow-attr
#![allow(clippy::all)]

use serde::Deserialize;

// ruleid: rs-no-allow-attr
#[allow(dead_code)]
fn silenced() {}

// ok: rs-no-allow-attr
#[expect(dead_code, reason = "exercised by the integration suite only")]
fn expected() {}

// ok: rs-no-allow-attr
fn main() {
    // ok: rs-no-allow-attr
    tauri_build::build()
}

// ok: rs-no-allow-attr
pub fn run(config: &Config) -> Result<(), tauri::Error> {
    // ok: rs-no-allow-attr
    tauri::Builder::default().run(tauri::generate_context!())
}

// ok: rs-no-serde-default
#[derive(Deserialize)]
pub struct Config {
    // ruleid: rs-no-serde-default
    #[serde(default)]
    pub port: u16,
    // ruleid: rs-no-serde-default
    #[serde(rename = "hostname", default = "localhost")]
    pub host: String,
    // ok: rs-no-serde-default
    #[serde(rename = "storage_root")]
    pub root: String,
    // ok: rs-no-serde-default
    pub version: String,
}
