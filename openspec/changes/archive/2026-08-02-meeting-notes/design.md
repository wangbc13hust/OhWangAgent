## Context

The agent already has the raw tools this needs — `file_write` (write the minutes),
`todo_write` (track action items), `file_read`/`web_fetch` (ingest material). What
is missing is a *contract*: today a meeting note is whatever the model improvises.
The system prompt (`ohwang/prompts.py`) only says the agent "helps with meeting
notes" generically. The existing scenario test asserts only that a file gets
written, not its structure, path, or todo sync.

## Goals / Non-Goals

**Goals:**
- Make minutes structurally consistent: meeting info / discussion+conclusions /
  action items.
- Land minutes at a deterministic path `docs/meetings/<date>-<topic>.md`.
- Push action items into the task list with status + priority.
- Never fabricate an owner/deadline the material doesn't state — mark 待确认.
- Verify all of the above with a scripted scenario test (no network/model).

**Non-Goals:**
- No audio/video transcription service integration — input is text material
  (pasted, or a notes file).
- No new permission mode, hooks, or policy caps.
- No change to the agent loop, provider layer, or context management.
- No dedicated `meeting_notes` *tool* — the existing tools already do the I/O.
- No new REPL command (e.g. `/meeting`) — the trigger stays the natural-language
  prompt; a dedicated command can be a follow-up change.

## Decisions

**D1. Implement as a prompt-level guide, not a new tool.**
A small `MEETING_NOTES_GUIDE` block appended to the system prompt fixes the
output contract (three sections, naming rule, 待确认 rule). Rationale: the loop
already has read/write/todo tools; a tool would duplicate that logic and add
permission surface. The guide is ~15 lines, so the system-prompt cost is
negligible. *Alternative considered:* a reusable skill — rejected for v0.3
because meeting notes is a core, always-available behavior; an on-demand skill
is a weaker guarantee than a prompt the model always sees. A skill can be
layered later for the fuller archive workflow.

**D2. Naming rule lives in the guide; a tiny helper service does sanitization.**
`docs/meetings/YYYY-MM-DD-<topic>.md` with the topic slugified (CJK-safe:
strip path separators). The helper (`ohwang/services/meeting_notes.py`) keeps the
name deterministic and unit-testable; it is committed for v0.3 because the
scenario test asserts the exact path, and a deterministic name helper removes
model variance from filename selection.

**D3. Todo sync reuses `todo_write` with explicit defaults.**
Each action item becomes a task-list entry: status `pending`, priority from the
material or defaulted to `medium`, owner/deadline copied from the minutes (待确认
where unknown). This keeps one authoritative task list that the user can see in
`/tasks`.

**Sequence (one run):**
1. Material arrives (pasted text or a notes-file path).
2. Agent reads the material (`file_read` / `web_fetch`).
3. Agent writes `docs/meetings/<date>-<topic>.md` via `file_write`.
4. Agent pushes action items via `todo_write`.
5. Agent reports the saved path and the number of action items.

## Risks / Trade-offs

- **LLM variance:** the structure is a prompt contract, so a weak model may still
  drift. Mitigation: the scenario test locks the observable shape (sections +
  path + todo entries); the guide's rules are explicit.
- **Overwrite:** two meetings on the same day/topic collide on the same filename.
  Accepted — `file_write` reports "Overwrote" and the date+topic pair is usually
  unique; a run-time suffix can be added later if needed.
- **Spec change vs existing test:** `test_scenario_meeting_notes` asserts the old
  behavior (a root-level filename, no structure/todo assertions). The delta
  intentionally changes this behavior, so the existing test must be updated in
  the same change — flagged in tasks 3.1.
- **Prompt size:** one extra block in the system prompt. Negligible against the
  existing context budget; kept to ~15 lines.
