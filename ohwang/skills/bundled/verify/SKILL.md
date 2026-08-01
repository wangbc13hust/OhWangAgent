---
name: verify
description: Verify that recent changes work correctly. Run tests and check for regressions.
allowed-tools: [bash, file_read, grep, glob]
---

You are in verify mode. Your job is to confirm that recent changes are correct.

Steps:
1. Identify what was recently changed (use git diff if available).
2. Run the project's test suite.
3. If any tests fail, analyze the failures and determine if they are caused by the recent changes.
4. Check for common issues: import errors, type mismatches, missing files.
5. Report a summary: what passed, what failed, and whether the changes are safe to ship.
