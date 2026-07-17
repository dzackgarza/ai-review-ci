# Test Proof Rules Database

This catalog lists test and assertion shapes that are structurally incapable of proving repository-owned behavior.
These are not weak patterns.
They are banned.

A test line is admissible only if it excludes a plausible broken implementation at the owned boundary.
If the line would pass on a broken, fake, partial, mocked, unwired, or review-appeasing implementation, it does not belong in the test suite.

Project tests prove product behavior.
Global QC polices code shape.
Issues record unresolved proof burdens.
Policy identity lives in `policies.md`; fixer-side restoration details live in `../../style-guide/references/style-guide-index.md`.

* * *

## Banned Shapes Are Not Checklists

The examples below are shapes, not literal-token rules.

Do not satisfy this policy by avoiding the exact variable names or exact APIs shown.
The pattern is banned whenever the assertion:
- checks existence instead of semantics;
- checks visibility instead of behavior;
- checks strings instead of structured errors;
- checks source shape instead of product behavior;
- checks helper branches instead of real boundaries;
- checks that a mock was called instead of checking a real effect;
- catches and inspects an exception instead of asserting a structured failure;
- catches or expects `AssertionError` as product behavior instead of treating assertions as provable state claims;
- would pass on arbitrary non-empty junk.

Variable names in examples are intentionally generic: `result`, `items`, `output_path`, `config_path`, `source`, `status`, `payload`, `boundary`, `helper`, `fallback`. They gesture at the general shape.

* * *

## **[TRY-CATCH-BAN]** Try/Catch Ban

Do not write try/catch/except/rescue blocks in tests or owned runtime code.

Banned:
- Python `try/except`
- JavaScript/TypeScript `try/catch`
- Ruby `begin/rescue`
- shell `cmd || fallback`, `set +e` around normal execution, or fallback branches
- Rust `let _ =`, `.ok()`, `unwrap_or`, `unwrap_or_else`, `match Err(_) => fallback`
- Catching or expecting assertion failures as the unit under test: Python `except AssertionError` / `pytest.raises(AssertionError)`, JavaScript `toThrow(AssertionError)`, or equivalents

Expected failures must be asserted by structured test-framework mechanisms or structured error values.
Unexpected failures must propagate.
Assertion failures are not expected product failures; they are failed proof claims about state.
A test may contain assertions, but it must not make catching an assertion failure the behavior being proved.

The only possible exception is an explicitly approved boundary renderer whose sole job is to translate a structured internal error into a user-facing protocol.
That boundary must not continue execution, must not default, and must not return partial success.

* * *

## **[REVIEW-RUBRIC]** Per-Assertion Review Rubric

For each assertion line, classify it:

- **Proof-bearing**: excludes a plausible broken implementation at the owned boundary.
- **Setup/synchronization**: may help the test run, but cannot be cited as proof.
- **Policing**: checks source shape or validator compliance; move to global QC.
- **Laundering**: makes a weak/fake artifact look intentionally scoped.
- **Junk-tolerant**: would pass on arbitrary non-empty output; delete.

A test passes review only if its proof-bearing assertions are sufficient without counting setup, policing, laundering, or junk-tolerant lines.

* * *

## **[LANG-AGNOSTIC-BANNED]** Language-Agnostic Banned Shapes

These are banned regardless of language:
- **[LA-EXISTENCE]** existence-only assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-VISIBILITY]** visibility-only assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-TRUTHY]** truthy/non-empty assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-STRING]** string assertion — `POLICY.NO_EXACT_STRING_PROOF`
- **[LA-TYPE]** type-only assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-SHAPE]** shape-only assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-NO-THROW]** no-throw assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-SOURCE-TEXT]** source-text assertion — `POLICY.GLOBAL_QC_AUTHORITY`
- **[LA-HELPER-BRANCH]** helper-branch assertion — `POLICY.NO_HELPER_PROOF`
- **[LA-BOOLEAN-FORCING]** boolean branch-forcing assertion — `POLICY.NO_HELPER_PROOF`
- **[LA-MOCK-COUNT]** mock/spy/call-count assertion — `POLICY.NO_MOCK_PROOF`
- **[LA-SNAPSHOT]** snapshot assertion where exact output is not the product — `POLICY.NO_SMOKE_PROOF`
- **[LA-IMPORT]** import/module-load/constructor assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-STATUS-LABEL]** status-label assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-LOG-WARNING]** log/warning assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-HTTP-STATUS]** HTTP status-only assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-DB-COUNT]** database count/existence assertion — `POLICY.NO_SMOKE_PROOF`
- **[LA-ROUND-TRIP]** round-trip assertion with shared implementation — `POLICY.NO_SMOKE_PROOF`
- **[LA-TIMING-PERF]** timing/performance assertion in ordinary tests — `POLICY.NO_SMOKE_PROOF`
- **[LA-NO-CONSOLE-ERRORS]** "no console errors" as sole proof — `POLICY.NO_SMOKE_PROOF`
- **[LA-COVERED-ELSEWHERE]** "covered elsewhere" with no exact proof anchor — `POLICY.NO_SMOKE_PROOF`

For every assertion line, force this question:
> **"What broken app would still pass this line?"**

If the answer is "many," ban the line.

* * *

## Python / pytest Banned Shapes

### **[PY-EXISTENCE]** Existence and non-null

**Ban:**
```python
def test_result_exists():
    result = run_owned_operation(input_payload)
    assert result is not None

def test_file_created(tmp_path):
    output_path = produce_artifact(tmp_path)
    assert output_path.exists()

def test_object_has_field():
    payload = load_payload()
    assert hasattr(payload, "items")
```
*Why banned:* A broken implementation can return `{}`, create an empty file, or attach a junk field.
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[PY-TRUTHY]** Truthy / non-empty

**Ban:**
```python
def test_items_returned():
    items = collect_domain_items(source_path)
    assert items

def test_output_has_content():
    output = render_document(markdown)
    assert len(output.html) > 0

def test_response_ok():
    response = call_boundary(request_payload)
    assert response.ok
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[PY-STRINGS]** String assertions

**Ban:**
```python
def test_missing_config_message(tmp_path):
    with pytest.raises(Exception) as exc:
        load_config(tmp_path / "missing.toml")
    assert "missing render_command" in str(exc.value)

def test_error_banner(page):
    page.click("button")
    assert "failed" in page.text_content("#status")
```
*Policy:* `POLICY.NO_EXACT_STRING_PROOF`.

### **[PY-SHAPE]** Shape-only assertions

**Ban:**
```python
def test_payload_shape():
    payload = build_payload(domain_input)
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"title", "body", "metadata"}

def test_items_are_models():
    items = collect_items(source)
    assert all(isinstance(item, DomainItem) for item in items)
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[PY-NO-THROW]** No-throw tests

**Ban:**
```python
def test_operation_does_not_crash():
    run_owned_operation(input_payload)

def test_config_loads(tmp_path):
    load_config(tmp_path / "app.toml")
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[PY-SOURCE-POLICING]** Source policing

**Ban:**
```python
def test_no_fallbacks_in_config_source():
    source = Path("src/config.py").read_text()
    assert "fallback" not in source
    assert "default" not in source

def test_no_type_ignore_comments():
    source = Path("src/module.py").read_text()
    assert "# type: ignore" not in source
```
*Why banned:* This belongs to global QC/static analysis, not project behavior tests.
*Policy:* `POLICY.GLOBAL_QC_AUTHORITY`.

### **[PY-HELPER-BRANCH]** Helper branch laundering

**Ban:**
```python
def test_existing_config_requires_explicit_values():
    error = require_or_default(
        value=None,
        config_exists=True,
        error_message="missing runtime.command",
        default_factory=lambda: "default-command",
    )
    assert error == "missing runtime.command"

def test_absent_config_uses_defaults():
    value = require_or_default(
        value=None,
        config_exists=False,
        error_message="must not be used",
        default_factory=lambda: 750,
    )
    assert value == 750
```
*Why banned:* The test passes the boolean that chooses the branch.
It does not construct an existing or absent config.
*Policy:* `POLICY.NO_HELPER_PROOF`.

### **[PY-TRY-EXCEPT]** Try/except in tests

**Ban:**
```python
def test_expected_failure():
    try:
        load_config(config_path)
    except Exception as error:
        assert "missing" in str(error)
```
*Policy:* `POLICY.NO_EXCEPTION_CONTROL_FLOW`.

### **[PY-MOCK-SPY]** Mock/spy/call-count

**Ban:**
```python
def test_calls_renderer(mocker):
    renderer = mocker.Mock()
    save_document(renderer, content)
    renderer.render.assert_called_once_with(content)

def test_network_path(monkeypatch):
    monkeypatch.setattr(client, "get", lambda url: {"ok": True})
    assert load_remote_data(url)
```
*Policy:* `POLICY.NO_MOCK_PROOF`.

* * *

## TypeScript / JavaScript Banned Shapes

### **[TS-EXISTENCE]** Existence / defined / truthy

**Ban:**
```ts
test("returns result", () => {
  const result = runOwnedOperation(inputPayload);
  expect(result).toBeDefined();
});

test("has items", () => {
  const items = collectDomainItems(sourceText);
  expect(items.length).toBeGreaterThan(0);
});

test("module exports function", async () => {
  const module = await import("../module");
  expect(module.render).toBeTruthy();
});
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[TS-VISIBILITY]** Visibility-only

**Ban:**
```ts
test("editor shell renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("preview-pane")).toBeVisible();
});

test("status is ready", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#status")).toContainText("ready");
});
```
*Why banned:* A totally broken app can render a shell and display "ready."
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[TS-STATUS-LABEL]** Status / label / banner assertions

**Ban:**
```ts
test("save shows success", async ({ page }) => {
  await page.getByRole("button", { name: /save/i }).click();
  await expect(page.locator("#status")).toContainText("saved");
});
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[TS-STRINGS]** String assertions

**Ban:**
```ts
test("shows error", async ({ page }) => {
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator(".error")).toContainText("render failed");
});

test("throws missing config", () => {
  expect(() => loadConfig(path)).toThrow("missing runtime.command");
});
```
*Policy:* `POLICY.NO_EXACT_STRING_PROOF`.

### **[TS-TYPE-SHAPE]** Type-only / shape-only

**Ban:**
```ts
test("returns array", () => {
  const items = collectItems(source);
  expect(Array.isArray(items)).toBe(true);
});

test("has html property", () => {
  const result = render(markdown);
  expect(result).toHaveProperty("html");
});
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[TS-NO-THROW]** No-throw

**Ban:**
```ts
test("does not throw", () => {
  expect(() => loadConfig(configPath)).not.toThrow();
});

test("promise resolves", async () => {
  await expect(runOperation(input)).resolves.toBeDefined();
});
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[TS-SOURCE-POLICING]** Source policing

**Ban:**
```ts
test("does not use any", () => {
  const source = readFileSync("src/fixture.ts", "utf8");
  expect(source).not.toContain("as any");
});

test("no fallbacks", () => {
  const source = readFileSync("src/config.ts", "utf8");
  expect(source).not.toContain("??");
  expect(source).not.toContain("||");
});
```
*Policy:* `POLICY.GLOBAL_QC_AUTHORITY`.

### **[TS-MOCKED-BOUNDARY]** Mocked boundary / browser smoke laundering

**Ban:**
```ts
test("browser shell renders", async ({ page }) => {
  await page.addInitScript(() => {
    window.__APP_INTERNALS__ = {
      invoke: async () => ({ ok: true, html: "<p>fake</p>" }),
    };
  });
  await page.goto("/");
  await expect(page.getByTestId("editor")).toBeVisible();
});
```
*Policy:* `POLICY.NO_MOCK_PROOF`.

### **[TS-SPY-COUNT]** Spy/call count

**Ban:**
```ts
test("save calls backend", async () => {
  const saveSpy = vi.fn();
  await saveDocument(saveSpy, content);
  expect(saveSpy).toHaveBeenCalledWith(content);
});

test("render invoked", async ({ page }) => {
  const invoke = vi.fn().mockResolvedValue({ ok: true });
  await runRender(invoke, "# Title");
  expect(invoke).toHaveBeenCalledTimes(1);
});
```
*Policy:* `POLICY.NO_MOCK_PROOF`.

### **[TS-TRY-CATCH]** Try/catch

**Ban:**
```ts
test("handles bad config", () => {
  try {
    loadConfig(path);
  } catch (error) {
    expect(String(error)).toContain("missing");
  }
});
```
*Policy:* `POLICY.NO_EXCEPTION_CONTROL_FLOW`.

* * *

## Rust Banned Shapes

### **[RS-IS_OK]** `is_ok`, `is_some`, length, existence

**Ban:**
```rust
#[test]
fn operation_succeeds() {
    let result = run_owned_operation(input_fixture());
    assert!(result.is_ok());
}

#[test]
fn file_exists() {
    let path = produce_artifact(tempdir.path()).unwrap();
    assert!(path.exists());
}

#[test]
fn items_present() {
    let items = collect_items(source_fixture());
    assert!(!items.is_empty());
}
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[RS-STRING-ERRORS]** Exact string errors

**Ban:**
```rust
#[test]
fn missing_config_errors() {
    let error = load_config(incomplete_config_path()).unwrap_err();
    assert_eq!(error.to_string(), "missing runtime.command");
}

#[test]
#[should_panic(expected = "missing runtime.command")]
fn config_panics() {
    load_config(incomplete_config_path()).unwrap();
}
```
*Policy:* `POLICY.NO_EXACT_STRING_PROOF`.

### **[RS-HELPER-BRANCH]** Helper branch proof

**Ban:**
```rust
#[test]
fn existing_config_requires_explicit_values() {
    let error = require_or_default::<String, _>(
        None,
        true,
        "missing runtime.command",
        || "default-command".to_string(),
    )
    .unwrap_err();
    assert_eq!(error, "missing runtime.command");
}
```
*Policy:* `POLICY.NO_HELPER_PROOF`.

### **[RS-BOOLEAN-FORCING]** Boolean branch-forcing

**Ban:**
```rust
#[test]
fn branch_for_existing_config() {
    let result = normalize_runtime(None, true);
    assert!(result.is_err());
}

#[test]
fn branch_for_absent_config() {
    let result = normalize_runtime(None, false);
    assert_eq!(result.unwrap(), RuntimeConfig::default());
}
```
*Policy:* `POLICY.NO_HELPER_PROOF`.

### **[RS-SOURCE-POLICING]** Source policing

**Ban:**
```rust
#[test]
fn no_defaults_in_config_source() {
    let source = std::fs::read_to_string("src/config.rs").unwrap();
    assert!(!source.contains("unwrap_or"));
    assert!(!source.contains("Default::default"));
}
```
*Policy:* `POLICY.GLOBAL_QC_AUTHORITY`.

### **[RS-SWALLOWED-ERROR]** Swallowed-error tests

**Ban:**
```rust
#[test]
fn cleanup_does_not_crash_when_file_missing() {
    cleanup_backup(missing_path()).unwrap();
}
```
*Policy:* `POLICY.NO_ERROR_DISCARD`.

### **[RS-PROCESS-LIFECYCLE]** Process lifecycle source-shape test

**Ban:**
```rust
#[test]
fn renderer_uses_kill_on_drop() {
    let source = std::fs::read_to_string("src/render.rs").unwrap();
    assert!(source.contains("kill_on_drop(true)"));
}
```
*Policy:* `POLICY.GLOBAL_QC_AUTHORITY`.

* * *

## Bash / Shell Banned Shapes

### **[SH-EXISTENCE]** Existence-only

**Ban:**
```bash
test -f "$output_file"
[ -s "$output_file" ]
[ -n "$result" ]
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[SH-GREP-STRINGS]** Grep string assertions

**Ban:**
```bash
grep -q "ready" "$log_file"
grep -q "success" "$output_file"
grep -q "missing runtime.command" "$stderr_file"
```
*Policy:* `POLICY.NO_EXACT_STRING_PROOF`.

### **[SH-STATUS]** Status-only

**Ban:**
```bash
curl -s "$url" >/tmp/response
test "$?" -eq 0

status="$(curl -s -o /dev/null -w '%{http_code}' "$url")"
test "$status" = 200
```
*Policy:* `POLICY.NO_SMOKE_PROOF`.

### **[SH-SUPPRESSION]** Suppression / fallback

**Ban:**
```bash
command_under_test 2>/dev/null || echo "ok"
grep -q pattern file || true
run_check >/dev/null 2>&1
```
*Policy:* `POLICY.NO_ERROR_DISCARD`.

### **[SH-SOURCE-POLICING]** Source policing

**Ban:**
```bash
! grep -R "unwrap_or" src
! grep -R "as any" src
! grep -R "fallback" src
```
*Policy:* `POLICY.GLOBAL_QC_AUTHORITY`.

* * *

## Final Language for the Skill

A test suite is not allowed to accumulate comforting facts.

Every assertion must carry proof weight.
If an assertion does not increase the epistemic status of the owned behavior, it is not neutral; it is false signal.
False signal is worse than no test because it teaches future agents that the burden is already discharged.

Ban the line.
