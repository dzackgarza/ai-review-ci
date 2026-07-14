# Boundary Test Bypass

> **Style card `BOUNDARY-BYPASS`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A test for a boundary condition (e.g., a null input, an edge case, a security check) tests the helper function that performs the check rather than the boundary where the check is enforced.

```python
# BAD: tests the helper, not the boundary
def test_sanitize_input():
    assert sanitize_input("<script>") == "&lt;script&gt;"

# The real question: does the endpoint reject or escape XSS?
```

## Preferred construction: Test the source-of-truth boundary — the public API, the route handler, the middleware, the validation gateway — not the internal helper.
If the helper is the boundary (standalone library function), test it there.
Otherwise, test through the boundary.

```python
# ## Preferred construction: test through the boundary
def test_xss_prevention():
    response = client.post("/comment", data={"text": "<script>alert('xss')</script>"})
    assert response.status_code == 200
    assert "<script>" not in response.text
```

## Use this pattern when:
- The test asserts behavior of an internal function that is called by a boundary function.
- The boundary function could change its implementation (e.g., use a different helper) and the test would still pass while the boundary behavior breaks.
- The failure mode is user-visible (crash, XSS, data loss) but the test only covers the internal helper.

## Choose a different pattern when:
- The helper function is a public reusable library with its own contract independent of the boundary.
- The boundary is explicitly tested separately and the helper test catches additional cases the boundary test cannot reach (pure logic, combinatorial).

<a id="remediation-string-based-error-types"></a>
