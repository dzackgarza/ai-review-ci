# Data-Peeking Inside Loops

> **Style card `DATA-PEEK`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A loop that checks a condition on each element and routes logic inside the loop body, mixing filtering with processing and making the control flow harder to read.

```python
# BAD: peeking inside the loop
results = []
for item in items:
    if item.status == "active":
        if item.owner is not None:
            results.append(process(item))
        else:
            logger.warning(f"item {item.id} has no owner")
    # items with other statuses are silently ignored
```

## Preferred construction: Filter and assert invariants before the loop.
The loop body should only contain the processing logic, with preconditions already satisfied.

```python
# ## Preferred construction: filter then process
active = [i for i in items if i.status == "active"]
assert all(i.owner is not None for i in active), "all active items must have an owner"
results = [process(i) for i in active]
```

## Use this pattern when:
- The filter conditions are knowable before the loop (no dependence on loop-local state).
- Filtering and processing can be separated without changing semantics.
- The loop body has 2+ conditional branches that route on element properties.
