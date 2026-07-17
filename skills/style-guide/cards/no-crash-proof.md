# No-Throw / No-Crash as Proof

> **Style card `NO-CRASH-PROOF`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A test calls a function and asserts nothing about the result — it only proves the function did not crash.
Examples: calling `run_operation()` without asserting on the output, asserting that `run()` returns without error but ignoring what it returns.

```python
# BAD: no-crash is not proof of correctness
def test_operation_does_not_crash():
    run_operation(input_data)  # no assertion — any output passes

def test_parse_does_not_raise():
    result = parse_document(text)  # result is never inspected
```

## Preferred construction: Assert exact output values or side effects.
A test that proves nothing about correctness is noise.
If the function returns a value, assert on it.
If the function produces a side effect (file write, database insert, API call), assert on the side effect's result.

```python
# ## Preferred construction: assert on the output
def test_operation_produces_correct_result():
    result = run_operation(input_data)
    assert result == ExpectedOutput(...)

# ## Preferred construction: assert on the side effect
def test_operation_writes_correct_file(tmp_path):
    output_path = run_operation(input_data, output_dir=tmp_path)
    assert output_path.read_text() == expected_content
```

## Use this pattern when:
- The test has no assertion on the function's output or side effects.
- The test would pass if the function returned `None` or produced no side effects.
- The only thing the test proves is that the code path was reachable.

## Choose a different pattern when:
- The function is a void-returning command whose correctness is verified by a separate integration test that asserts on the system state.
- The function genuinely has no observable output and is tested through its caller's boundary.

<a id="remediation-mockspycall-count-as-proof"></a>
