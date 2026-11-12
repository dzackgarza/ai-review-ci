// POLICY.NO_HIDDEN_CONFIG governs the configuration surface of a program. A
// test file is no such surface: its constants are the fixed inputs of a
// proof, and a proof with a configurable input proves nothing determinate.

// ok: no-const-assignment
const WEB_PAGE_URL = "https://example.org/genus";
// ok: no-const-assignment
const DATA_URL = `data:image/png;base64,iVBORw0KGgo=`;
// ok: no-const-assignment
const NO_DOC_PATH = "";
// ok: no-const-assignment
const RENDER_TIMEOUT_MS = 30000;
