## Purpose

Persists conversation history so a run can be saved, listed, and resumed:
timestamped session files under .ohwang/sessions with previews, summaries, and
message counts surfaced for later selection.

## Requirements

### Requirement: Sessions persist to per-session files
The system SHALL save a conversation as a JSON file under .ohwang/sessions with a
timestamp-based id, and SHALL disambiguate ids saved within the same second so
no file overwrites another.

#### Scenario: Save writes a unique file
- **WHEN** a conversation is saved
- **THEN** a new JSON file with a unique timestamp-based id is written

#### Scenario: Same-second saves stay distinct
- **WHEN** two saves happen within the same second
- **THEN** the second file gets a numeric suffix rather than overwriting the first

### Requirement: Listing surfaces metadata
The system SHALL list sessions newest-first, each showing its id, modification
time, preview, summary, and message count. Unreadable session files SHALL be
skipped in the listing.

#### Scenario: Sessions list newest-first
- **WHEN** sessions are listed
- **THEN** they appear sorted by modification time, newest first, with metadata

#### Scenario: Corrupt sessions are skipped
- **WHEN** a session file cannot be parsed
- **THEN** it is omitted from the listing

### Requirement: Load by id
The system SHALL load a session's messages by its id, returning nothing for an
unknown or unreadable id.

#### Scenario: Existing session loads
- **WHEN** a session id matches a saved file
- **THEN** its messages are returned for resumption

#### Scenario: Unknown id returns empty
- **WHEN** the requested id does not exist
- **THEN** no messages are returned
