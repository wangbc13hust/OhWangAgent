## Purpose

Turns raw meeting material into dependable, structured meeting minutes: a fixed
document layout, a deterministic output path, and action items pushed into the
task list, so every run produces verifiable, archivable output.

## ADDED Requirements

### Requirement: Structured minutes format
The system SHALL generate meeting minutes in markdown with three sections:
meeting info (date, topic, participants), discussion with conclusions/decisions,
and action items. Each action item SHALL carry an owner and a deadline whenever
the source material supports them.

#### Scenario: Minutes contain the standard sections
- **WHEN** the agent produces minutes from a transcript or rough notes
- **THEN** the markdown has meeting info, discussion and conclusions, and action items

#### Scenario: Action items carry owner and deadline
- **WHEN** the source material names a responsible person and a date
- **THEN** the action item records both

#### Scenario: Missing metadata is flagged in place
- **WHEN** the material does not name the participants, the date, or the topic
- **THEN** the field still appears in its section, marked 待确认 rather than omitted silently

#### Scenario: Meeting without action items
- **WHEN** the meeting produced no action items
- **THEN** the action-items section states that there are none

### Requirement: Deterministic output location
The system SHALL write the minutes to a file under docs/meetings/ named with the
meeting's date and topic (for example 2026-08-02-周会.md), using the date stated
or implied in the material, or the current date when the material gives none, and
creating the directory when it does not exist.

#### Scenario: Minutes land in the meetings directory
- **WHEN** minutes are saved
- **THEN** they are written to docs/meetings/<date>-<topic>.md

#### Scenario: Undated material uses the current date
- **WHEN** the material gives no meeting date
- **THEN** the current date is used in the filename

#### Scenario: Directory is created as needed
- **WHEN** docs/meetings does not exist yet
- **THEN** it is created before the minutes are written

### Requirement: Action items sync to the task list
The system SHALL push the meeting's action items into the agent's task list, each
with a status and a priority, so follow-up work is tracked rather than left only
in the document.

#### Scenario: Action items appear in the task list
- **WHEN** minutes contain action items
- **THEN** corresponding entries exist in the task list with status and priority

### Requirement: Source fidelity with explicit uncertainty
The system SHALL derive conclusions and action items only from the meeting
material and SHALL mark anything it cannot confirm as 待确认 instead of
inventing a value.

#### Scenario: Uncertain fields are flagged
- **WHEN** the material does not state an owner, a deadline, or other metadata
- **THEN** the missing field is marked 待确认 rather than fabricated
