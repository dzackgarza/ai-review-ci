# Mock/Spy/Call-Count as Proof

> **Style card `MOCK-AS-PROOF`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A test asserts that a mock was called, or called N times, with certain arguments, without asserting on the real effect at the boundary.
The mock assertion proves the internal wiring is connected but not that the system produces correct output.

```python
# BAD: asserts mock was called, not that output is correct
def test_sends_notification():
    mock_send = Mock()
    notifier = Notifier(mock_send)
    notifier.notify(user_email)
    assert mock_send.called
    mock_send.assert_called_once_with(to=user_email, body="...")
```

## Preferred construction: Assert on the real boundary effect — the file that was written, the database row that was inserted, the API response that was returned.
If the code path is simple enough that a mock assertion is the only way to verify it, consider whether the test adds value at all (the path is trivially correct by inspection) or whether an integration test would cover it.

```python
# ## Preferred construction: assert on the real effect
def test_notification_logged_in_database():
    service.notify(user_email)
    log_entry = Log.query.filter_by(email=user_email).first()
    assert log_entry is not None
    assert expected_body in log_entry.body
```

## Use this pattern when:
- The primary assertion is on mock call count or call arguments.
- No real boundary effect is verified (no database, no file, no API response).
- The mock is standing in for a side effect that is observable in the test environment.

## Choose a different pattern when:
- The boundary is an external API that cannot be called in tests (third-party service, hardware) AND the mock is paired with a separate integration test that verifies the real interaction.
- The mock assertion is supplementary to a real boundary assertion.

<a id="remediation-source-policing-in-tests"></a>
