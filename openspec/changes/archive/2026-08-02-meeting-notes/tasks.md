## 1. Contract in the system prompt

- [x] 1.1 Add `MEETING_NOTES_GUIDE` to `ohwang/prompts.py`: three-section layout,
      `docs/meetings/YYYY-MM-DD-<topic>.md` naming rule, and the 待确认 rule.
- [x] 1.2 Append it in `build_system_prompt()` so it is always present.
- [x] 1.3 Existing prompt tests still pass (`tests/test_prompts.py` or equivalent).

## 2. Naming helper (small, committed)

- [x] 2.1 Add `ohwang/services/meeting_notes.py` with a slugify/date helper for the
      target filename; export from `ohwang/services/__init__.py`.
- [x] 2.2 Unit-test the helper with CJK and path-separator cases.

## 3. Scenario test asserting the contract

- [x] 3.1 Update `test_scenario_meeting_notes` — it currently asserts the OLD
      behavior (root-level `meeting-*.md`, no structure/todo assertions) that this
      delta intentionally changes. Move it to the new contract: minutes at
      `docs/meetings/<date>-<topic>.md` with the three sections, and action items
      in the todo store with status + priority.
- [x] 3.2 Add cases for the 待确认 rules: a transcript with no owner/deadline, and
      a meeting with no action items — both must not fabricate values.

## 4. Docs

- [x] 4.1 `docs/CHANGELOG.md` entry for the capability.
- [x] 4.2 `docs/ARCHITECTURE.md` note if `meeting_notes.py` is kept.

## 5. Green suite

- [x] 5.1 Run `.venv\Scripts\python.exe -m pytest -q` — full suite green before commit.
