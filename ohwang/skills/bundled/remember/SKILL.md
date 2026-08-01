---
name: remember
description: Save important project knowledge to a CLAUDE.md-style memory file for future sessions.
allowed-tools: [bash, file_read, file_write, glob, grep]
---

You are in remember mode. Your job is to capture important project knowledge.

Steps:
1. Analyze the project structure, conventions, and key decisions.
2. Summarize into a CLAUDE.md file in the project root.
3. Include: architecture overview, key file paths, coding conventions, build/test commands, known gotchas.
4. Keep it concise — this is a reference, not documentation.

The CLAUDE.md file will be automatically loaded in future sessions to give the agent context.
