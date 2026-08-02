## Purpose

Gives the agent read, write, and edit access to the filesystem: reading files in
whole or in slices, creating and overwriting files, and performing exact-string
edits with ambiguity guards, plus search utilities for navigating the tree.

## Requirements

### Requirement: Read files in slices
The file read tool SHALL return a file's contents, with optional 1-indexed line
offset and limit for large files, numbering the returned lines and reporting an
error for a missing file or a read failure.

#### Scenario: Whole file read
- **WHEN** a file is read without offset or limit
- **THEN** its full contents are returned with line numbers

#### Scenario: Sliced read
- **WHEN** an offset and limit are given
- **THEN** only that line range is returned

#### Scenario: Missing file is an error
- **WHEN** the requested path does not exist
- **THEN** an error result names the missing file

### Requirement: Write and overwrite files
The file write tool SHALL create or overwrite a file, creating parent
directories as needed, and SHALL report whether the file was created or
overwritten together with the byte count.

#### Scenario: New file created
- **WHEN** a file is written to a path that does not exist
- **THEN** it is created, parents included, and the result says so

#### Scenario: Existing file overwritten
- **WHEN** a file is written to an existing path
- **THEN** it is overwritten and the result says so

### Requirement: Exact-string edits with ambiguity guards
The file edit tool SHALL replace an exact string in a file. A missing or
ambiguous old_string SHALL fail rather than guess: if old_string is absent the
edit errors, and if it occurs more than once the edit errors unless replace_all
is set.

#### Scenario: Unique match replaces
- **WHEN** old_string occurs exactly once
- **THEN** it is replaced and the result reports one occurrence

#### Scenario: Ambiguous match refuses without replace_all
- **WHEN** old_string occurs multiple times and replace_all is false
- **THEN** the edit errors and asks for more context

#### Scenario: No match errors
- **WHEN** old_string is not present in the file
- **THEN** the edit errors without modifying the file

### Requirement: Edit requires exact match
The file edit tool SHALL only perform replacements where the target string
matches exactly, so a whitespace mismatch cannot silently alter the wrong spot.

#### Scenario: Non-exact text is not replaced
- **WHEN** the file's text differs from old_string in whitespace or casing
- **THEN** the edit is refused
