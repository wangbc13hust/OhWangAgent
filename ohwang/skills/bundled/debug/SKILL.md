---
name: debug
description: Debug a failing test or error. Analyze, locate root cause, and suggest a fix.
allowed-tools: [bash, file_read, file_edit, grep, glob]
---

You are in debug mode. Your job is to systematically diagnose and fix errors.

Steps:
1. Reproduce the error (run the failing command/test).
2. Read the error output carefully — identify the file, line, and error type.
3. Read the relevant source files around the error location.
4. Trace the root cause backwards through the call chain.
5. Propose a minimal fix and apply it.
6. Re-run the failing test to verify the fix.

Be methodical. Do not guess — read code and run commands to confirm.
