# Backend Testing Guide

## Run the test suite

Activate the project virtual environment, then run:

```powershell
python -m pytest tests -v
```

## Check the results

Review the test summary for passed, failed, or skipped tests.

If a test fails, investigate the cause before merging further changes.

## Before pushing changes

1. Run the test suite.
2. Review git status.
3. Inspect git diff --check.
4. Commit only the intended files.
