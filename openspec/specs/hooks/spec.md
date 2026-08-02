## Purpose

Exposes lifecycle and tool-use events so the operator can attach their own
checks and side-effects — Python callbacks or shell commands — around the agent
loop without modifying its code.

## Requirements

### Requirement: Lifecycle event set
The system SHALL fire nine events: pre-tool-use, post-tool-use, notif, stop,
user-prompt-submit, session-start, session-end, subagent-start, and
subagent-stop.

#### Scenario: Tool-use events fire around execution
- **WHEN** a tool call is about to run, and again after it completes
- **THEN** pre-tool-use and post-tool-use events fire

#### Scenario: Session and prompt events
- **WHEN** a REPL session starts and ends, and when a run is submitted and stops
- **THEN** session-start, session-end, user-prompt-submit, and stop events fire

### Requirement: Pre-tool hooks can block or rewrite
A pre-tool-use hook SHALL be able to block a tool call or replace its input.
Blocking SHALL be signaled by a falsey return, a block marker, or a nonzero exit
code from a configured command.

#### Scenario: Python handler blocks
- **WHEN** a pre-tool-use handler returns a block signal
- **THEN** the tool is not executed and the model receives an error result

#### Scenario: Command hook blocks on nonzero exit
- **WHEN** a configured hook command exits nonzero
- **THEN** the tool is blocked and the reason comes from the command output

#### Scenario: Handler rewrites input
- **WHEN** a pre-tool-use handler returns an input replacement
- **THEN** the tool executes with the replaced input

### Requirement: Command hooks are configured in hooks.json
The system SHALL load command hooks from .ohwang/hooks.json, keyed by event, with
an optional tool filter matched as a glob. Hook commands SHALL run with a bounded
timeout and never block the agent loop indefinitely.

#### Scenario: Configured command hooks run
- **WHEN** hooks.json defines command hooks for an event
- **THEN** each matching command runs and its result affects the event

### Requirement: Event handlers never break the loop
Notification-style event handlers SHALL run non-blocking and SHALL swallow their
own errors so a broken hook cannot crash the agent loop.

#### Scenario: Broken handler is ignored
- **WHEN** a registered handler raises while an event fires
- **THEN** the error is swallowed and the agent loop continues
