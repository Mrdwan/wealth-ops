---
description: how to run the test suite
---

# Run Tests

The project uses Docker for test execution (Python 3.13 container, all dependencies pre-installed via Poetry).

// turbo-all

1. Run the full test suite:
```bash
docker compose --profile test run --rm test pytest -v --tb=short
```

2. Verify the output shows:
   - **0 failures**
   - **100% branch coverage** (enforced by `--cov-fail-under=100` in `pyproject.toml`)

3. If any tests fail or coverage drops below 100%, fix the issues before finishing the session.

## Notes
- Tests use `moto` for AWS mocking — no real AWS calls.
- The Docker image is based on `Dockerfile.test` and uses `poetry install --only main,dev`.
- Pre-commit hook (`pytest-docker`) also runs the same command on every commit.
