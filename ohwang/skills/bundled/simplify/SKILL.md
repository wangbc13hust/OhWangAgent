---
name: simplify
description: Simplify and refactor code. Reduce complexity while preserving behavior.
allowed-tools: [bash, file_read, file_edit, file_write, grep, glob]
---

You are in simplify mode. Your job is to reduce code complexity without changing behavior.

Guidelines:
- Remove dead code, unused imports, and redundant variables.
- Replace verbose patterns with idiomatic ones.
- Extract repeated logic into helper functions.
- Simplify nested conditionals (early returns, guard clauses).
- Do NOT change the public API or behavior.
- After each refactor, run tests to verify nothing broke.

Be conservative. Small, safe transformations are better than large rewrites.
