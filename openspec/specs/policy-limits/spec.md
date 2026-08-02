## Purpose

Stops runaway agent loops by capping how many tool calls may execute in a run —
both in total and per tool — with limits that an operator can tune in a local
policy file.

## Requirements

### Requirement: Total and per-tool call caps
The system SHALL enforce a maximum number of tool calls per run and MAY impose a
separate cap per tool name. A call that would exceed either cap SHALL be refused.

#### Scenario: Total cap reached
- **WHEN** the total number of tool calls in a run reaches the configured maximum
- **THEN** further tool calls are refused

#### Scenario: Per-tool cap reached
- **WHEN** a single tool has executed its per-tool limit
- **THEN** further calls to that tool are refused even while the total is below its cap

### Requirement: Limits load from policy.json
The system SHALL load the total cap and per-tool caps from .ohwang/policy.json.
A missing or malformed policy file SHALL fall back to built-in defaults rather
than crashing, and entries MAY be omitted to use defaults per tool.

#### Scenario: Policy file applies
- **WHEN** .ohwang/policy.json defines max_tool_calls or per_tool limits
- **THEN** those values govern the run

#### Scenario: Missing policy falls back to defaults
- **WHEN** no policy file exists or it is malformed
- **THEN** the built-in defaults apply

### Requirement: Usage counting
The system SHALL record each executed tool call against both the total counter and
its per-tool counter so caps reflect calls that actually ran.

#### Scenario: Counts accumulate per call
- **WHEN** a tool call executes
- **THEN** the total counter and that tool's counter each increase by one
