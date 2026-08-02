## Purpose

Executes shell commands — bash and powershell — in a shared runner that streams
live output when a terminal is present and returns a final result block for the
model, with a timeout so runaway commands are killed.

## Requirements

### Requirement: Bash and powershell tools
The system SHALL provide bash and powershell tools that execute a command string
through a shared execution path, each with its own tool name and default
permission of ask.

#### Scenario: Command executes and returns output
- **WHEN** a shell tool runs a command
- **THEN** stdout, stderr, and the return code are returned to the model

#### Scenario: Missing command is refused
- **WHEN** a shell tool call has no command
- **THEN** the call fails with an error result

### Requirement: Configurable timeout with kill
Each shell call SHALL accept a timeout in seconds, defaulting to 120, and SHALL
kill a command that overruns it, returning a timeout signal rather than hanging
the loop.

#### Scenario: Command completes within the timeout
- **WHEN** a command finishes before its timeout
- **THEN** its real output and exit code are returned

#### Scenario: Command overruns and is killed
- **WHEN** a command exceeds its timeout
- **THEN** it is killed and a timed-out result is returned

### Requirement: Live streaming to a terminal
When a terminal is attached, the shell runner SHALL forward incremental stdout
and stderr as the command runs, so a long task shows progress; the final result
block SHALL stay identical whether or not streaming is active.

#### Scenario: TTY sessions stream live output
- **WHEN** a terminal is attached and a command runs
- **THEN** output lines appear as they are produced

#### Scenario: Non-TTY stays quiet
- **WHEN** no terminal is attached
- **THEN** no live streaming occurs and only the final block is produced
