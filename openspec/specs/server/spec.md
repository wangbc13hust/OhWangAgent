## Purpose

Runs the office agent as a local always-on service so a web front and the CLI
share one agent kernel over an HTTP/WS transport, with single-flight execution
and session persistence.

## Requirements

### Requirement: Local daemon with localhost-only binding
The system SHALL start a localhost daemon through `ohwang serve` that serves the
agent over HTTP, SHALL listen only on 127.0.0.1, SHALL expose a health endpoint
that reports readiness, and SHALL exit cleanly when shutdown is requested. The
daemon SHALL NOT require authentication or any account setup.

#### Scenario: Daemon starts and reports ready
- **WHEN** `ohwang serve` is started
- **THEN** an HTTP endpoint responds on localhost and the health endpoint reports ready

#### Scenario: Localhost-only binding
- **WHEN** the daemon starts
- **THEN** it binds to 127.0.0.1 and is not reachable from other hosts

#### Scenario: Clean shutdown
- **WHEN** shutdown is requested
- **THEN** the server stops accepting work, in-flight requests are either completed or rejected cleanly, and the port is released

### Requirement: Single-flight request execution
The system SHALL execute agent runs one at a time: a run that arrives while
another is active SHALL wait for it to finish rather than run concurrently. The
same single-flight lock SHALL serialize the REPL, the web transport, and
scheduled runs, and each completed request SHALL return the run's final text.

#### Scenario: Second request waits
- **WHEN** a second run arrives while a first run is still executing
- **THEN** the second run waits and executes only after the first completes

#### Scenario: Run returns final text
- **WHEN** a request's run completes
- **THEN** the response carries the agent's final text

### Requirement: Streaming progress events
The system SHALL expose a persistent streaming channel that emits the agent's
progress events — text fragments, tool calls, tool results with their error
state, compaction notices, and per-turn progress — so a client can render the
same feedback the terminal shows.

#### Scenario: Progress streams before completion
- **WHEN** a run is started over the streaming channel
- **THEN** text and tool events are delivered incrementally before the final result

#### Scenario: Tool results carry error state
- **WHEN** a tool call returns an error
- **THEN** the client receives the result flagged as an error

### Requirement: Session-backed conversations
The system SHALL persist each web conversation as a session, SHALL create a new
session for a conversation that names none, and SHALL continue an existing
conversation from its saved history when a request names its session.

#### Scenario: New conversation creates a session
- **WHEN** a first message arrives without a session id
- **THEN** a new session is created and its id is returned to the client

#### Scenario: Resuming reuses history
- **WHEN** a request names an existing session
- **THEN** the agent continues from that session's saved history
