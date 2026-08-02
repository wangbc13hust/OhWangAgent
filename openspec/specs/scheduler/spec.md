## Purpose

Runs prompts on a schedule in the background: a persisted cron-style job store
with a polling thread that hands each due prompt to the agent and keeps state
across restarts.

## Requirements

### Requirement: Cron jobs with five-field expressions
The system SHALL support cron-style jobs defined by an id, a five-field
expression, and a prompt. The expression SHALL support stars, lists, ranges, and
step values, and SHALL validate against the five-field bounds before a job is
accepted.

#### Scenario: Valid expression is accepted
- **WHEN** a job is added with a well-formed five-field expression
- **THEN** it is stored and scheduled

#### Scenario: Invalid expression is rejected
- **WHEN** a job is added with a malformed expression or wrong field count
- **THEN** the job is rejected and no job is created

### Requirement: Background polling with one-second resolution
The scheduler SHALL run a background thread that evaluates due jobs each second,
firing each job whose expression matches the current time and whose last run is
older than a short cooldown so a job does not fire twice within one minute.

#### Scenario: Due job fires
- **WHEN** the current minute matches a job's expression and the cooldown has elapsed
- **THEN** the job's prompt is handed to the agent runner

#### Scenario: Freshly run job is skipped
- **WHEN** a job fired within the cooldown window
- **THEN** it is not fired again on the same poll

### Requirement: Persisted job state
Jobs SHALL persist to a state file so they survive restarts, and adding or
removing a job SHALL update the file. A corrupt or unreadable state file SHALL
not prevent the scheduler from starting.

#### Scenario: Jobs survive restart
- **WHEN** the scheduler restarts
- **THEN** previously saved jobs are restored from the state file

#### Scenario: Corrupt state is ignored
- **WHEN** the state file is unreadable
- **THEN** the scheduler starts with no jobs instead of failing

### Requirement: Failure isolation
A job whose prompt raises in the runner SHALL be contained: the exception SHALL
be swallowed and the scheduler SHALL keep polling the remaining jobs.

#### Scenario: One failing job does not stop the scheduler
- **WHEN** a fired job's runner raises
- **THEN** the error is contained and subsequent polls continue
