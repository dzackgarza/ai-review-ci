// POLICY.NO_HIDDEN_CONFIG: a constant whose name has a configuration word as
// one of its `_`-separated segments, and whose value is a literal. A word
// inside a longer word (PORT in EXPORT) is no such segment.

// ruleid: no-const-assignment
const API_URL = "https://api.example.org/v1";
// ruleid: no-const-assignment
const DEFAULT_PORT = 8080;
// ruleid: no-const-assignment
export const REQUEST_TIMEOUT_MS = 500;
// ruleid: no-const-assignment
const SEARCH_PATHS = ["/usr/share", "/usr/local/share"];
// ruleid: no-const-assignment
const MAX_RETRIES = 3;
// ruleid: no-const-assignment
const TOKEN = "s3cr3t";
// ruleid: no-const-assignment
const MIRROR = "https://mirror.example.org/";

// ok: no-const-assignment
const EXPORT_MENU_ITEM = "menu.export";
// ok: no-const-assignment
const NEXT_FAILURE_REPORTED_MS = 1_500;
// ok: no-const-assignment
const NO_PORTAL_FILE_CHOOSER_VERSION = 1000;
// ok: no-const-assignment
const SUPPORTED_FORMATS = ["markdown", "latex"];
// ok: no-const-assignment
const DIRECTIONS = ["ascending", "descending"];
// ok: no-const-assignment
const TOKENIZER_NAME = "words";
