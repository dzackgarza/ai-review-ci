# Existence / Truthy / Shape as Proof

> **Style card `EXISTENCE-AS-PROOF`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A test asserts only that a value exists, is truthy, non-empty, or has the right type/shape, without checking its semantic content.
Examples: `assert result is not None`, `assert items`, `assert len(output) > 0`, `assert isinstance(result, dict)`, `assert hasattr(payload, "items")`, `expect(result).toBeDefined()`.

```python
# BAD: asserts existence, not semantics
def test_result_exists():
    result = run_owned_operation(input_payload)
    assert result is not None

def test_items_returned():
    items = collect_domain_items(source_path)
    assert items  # truthy — empty list would also fail but for wrong reason

def test_file_created(tmp_path):
    output_path = produce_artifact(tmp_path)
    assert output_path.exists()  # empty file passes
```

These assertions pass even on broken output: `None` proves nothing; an empty file exists; a junk dict `{"x": 1}` is truthy.

## Preferred construction: Assert on exact expected values against real fixtures.
The assertion should prove the output is correct, not just that it exists.
Every existence assertion should be replaceable with a concrete value assertion against known test fixtures.

```python
# ## Preferred construction: assert exact semantics against fixtures
def test_artifact_contains_expected_semantics(tmp_path):
    output_path = produce_artifact(tmp_path, source=fixture_path("valid_input.md"))
    assert output_path.read_text() == expected_text("valid_output.html")

def test_collects_expected_ordered_items():
    items = collect_domain_items(fixture_path("source_with_two_items.md"))
    assert items == [
        DomainItem(key="alpha", title="First"),
        DomainItem(key="beta", title="Second"),
    ]

def test_loads_correct_payload():
    payload = load_payload(fixture_path("config.toml"))
    assert payload == {"host": "localhost", "port": 8080}
```

## Use this pattern when:
- The assertion proves only that a value exists (is not None, is truthy, is non-empty, has a field) but not that the value is correct.
- A broken implementation could return a plausible-looking but wrong value and the test would still pass.

## Choose a different pattern when:
- The existence check is one assertion among many in a test that also verifies semantic content (e.g., a precondition guard before the real assertion).
- The test is explicitly a liveness/health check that only needs to prove the endpoint responds.

<a id="remediation-no-throw--no-crash-as-proof"></a>
