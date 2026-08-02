## Purpose

Decides, per tool call, whether the model may run a tool — mode-aware and
rule-aware — so destructive operations require approval while research sessions
stay read-only.

## Requirements

### Requirement: Four permission modes
The system SHALL support default, plan, auto, and bypass modes. In default mode
each tool follows its default permission or a matching rule; in plan mode only
read-only tools pass; auto mode approves every call; bypass mode skips all checks.

#### Scenario: Default mode follows tool defaults
- **WHEN** a tool whose default permission is "allow" is requested in default mode
- **THEN** it runs without asking

#### Scenario: Plan mode blocks writes and shells
- **WHEN** a write or shell tool is requested while in plan mode
- **THEN** it is denied

#### Scenario: Auto and bypass modes
- **WHEN** a tool call is requested in auto or bypass mode
- **THEN** it is allowed without checks

### Requirement: Rule precedence is deny-first
The system SHALL resolve a tool's decision from the allow, ask, and deny glob
lists and any per-tool rules, with precedence deny > allow > ask > per-tool rule
> tool default. A deny rule SHALL win even over a remembered "always" grant.

#### Scenario: Deny overrides allow
- **WHEN** a tool name matches both a deny rule and an allow rule
- **THEN** the call is denied

#### Scenario: Glob patterns apply
- **WHEN** a rule uses a glob such as mcp__*
- **THEN** it matches every tool whose name fits the pattern

#### Scenario: Unspecified tools fall back to their default
- **WHEN** a tool has no matching rule
- **THEN** its own default permission decides

### Requirement: Interactive approval with remembered grants
For a tool whose decision is ask, the system SHALL prompt the user and MAY
remember an "always" answer for the specific tool-and-argument signature so the
same call passes without re-asking.

#### Scenario: Always remembered for a signature
- **WHEN** the user answers "always" for a tool on a given file or command
- **THEN** subsequent identical calls pass without asking

### Requirement: Plan-mode exit requires approval
Leaving plan mode SHALL require explicit user approval; with non-interactive
stdin approval SHALL default to deny so a session cannot silently regain write
access.

#### Scenario: Non-interactive exit is denied
- **WHEN** exit_plan_mode is requested with non-interactive stdin
- **THEN** the session stays read-only unless the user approves

### Requirement: CLI selects and toggles the mode
The CLI SHALL select the initial mode from flags: --plan starts in plan mode,
-y/--auto-approve starts in auto mode, otherwise default mode. The mode SHALL be
changeable at runtime.

#### Scenario: Plan flag starts read-only
- **WHEN** the agent starts with --plan
- **THEN** the session begins in read-only plan mode

#### Scenario: Auto-approve toggles at runtime
- **WHEN** the user toggles auto-approve during a session
- **THEN** the session switches between default and auto mode
