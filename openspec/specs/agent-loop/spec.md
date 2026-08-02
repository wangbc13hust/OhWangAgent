## Purpose

Drives the agentic loop that turns a user request into model-generated text and
tool calls, executes every call through a permissioned, guarded pipeline, and
returns a final answer without ever crashing the session.

## Requirements

### Requirement: A run starts from a user prompt and ends with a final answer
The system SHALL accept a user prompt, append it to the conversation, and run an
iterative loop that streams model output and executes any requested tool calls.
The loop SHALL stop after at most 50 iterations when the model has not already
produced a final answer.

#### Scenario: Single-turn answer
- **WHEN** a user submits a prompt and the model returns only text
- **THEN** the run ends and returns the accumulated text as the final answer

#### Scenario: Tool-driven turn continues the loop
- **WHEN** the model returns one or more tool calls
- **THEN** each call is executed and its result is appended to the conversation as a tool result, and the loop continues to the next turn

#### Scenario: Iteration ceiling
- **WHEN** a run reaches 50 iterations without the model producing a final answer
- **THEN** the run ends and returns whatever text has accumulated so far

### Requirement: Tool calls flow through a guarded execution pipeline
Each tool call SHALL pass through hook checks, permission checks, and policy
budget checks before its implementation runs. A tool that fails any check SHALL
produce an error result block and MUST NOT execute.

#### Scenario: Pre-tool hook blocks a call
- **WHEN** a pre-tool-use hook blocks the tool
- **THEN** the tool is not executed and the model receives an error result whose content names the hook as the blocker

#### Scenario: Permission denial still counts toward the budget
- **WHEN** a tool call is denied by permissions
- **THEN** the tool is not executed, an error result is returned, and the denied call is still recorded against the policy budget

#### Scenario: Policy budget exhausted
- **WHEN** the policy budget for a tool is exhausted
- **THEN** the tool is not executed and the model receives an error result naming the policy limit

#### Scenario: Tool raises an unexpected exception
- **WHEN** a tool's implementation raises an exception
- **THEN** the run converts it into an error result block and continues the loop instead of crashing

### Requirement: Unknown tool calls are reported, not executed
When the model requests a tool that is not registered, the system SHALL return an
error result block and continue the run.

#### Scenario: Unregistered tool name
- **WHEN** the model emits a tool call whose name is not registered
- **THEN** the model receives an error result identifying the unknown tool

### Requirement: Oversized tool results are trimmed before the next model call
Before each turn, tool-result blocks whose content exceeds 30,000 characters
SHALL be replaced with a marker noting the original length. Messages themselves
SHALL NOT be dropped.

#### Scenario: Giant file read stays bounded
- **WHEN** a tool result contains more than 30,000 characters
- **THEN** its content is replaced by a marker such as "[Old tool result content cleared (was N chars)]" before the next model call

### Requirement: Prompt-too-long responses trigger a single retry
When the model API rejects the request because the conversation is too long, the
system SHALL compact the conversation and retry the same turn exactly once. If
compaction does not shrink the conversation, the error SHALL propagate.

#### Scenario: Too-long error is recovered by compaction
- **WHEN** the API rejects the request as too long and compaction reduces the conversation size
- **THEN** the same turn is retried once with the compacted conversation

#### Scenario: Compaction that does not shrink aborts the retry
- **WHEN** the API rejects the request as too long but compaction does not reduce the message count
- **THEN** the error propagates and the run does not retry endlessly

### Requirement: The effective system context is assembled per run
The system prompt SHALL be composed from the base prompt plus, when present, the
current git context, the current todo list, memory facts relevant to the latest
user message, and any session summary. The composed context SHALL be cached and
rebuilt whenever the conversation or its inputs change.

#### Scenario: Git state is injected
- **WHEN** the agent runs inside a git repository
- **THEN** the system context includes the branch name, the five most recent commits, and a summary of working-tree changes

#### Scenario: Relevant memories are surfaced
- **WHEN** memory facts score as relevant to the latest user message
- **THEN** they are rendered into the system context under their own section

### Requirement: Run lifecycle events are emitted
The system SHALL emit a submit event when a run begins and a stop event when a
run completes, carrying the final text.

#### Scenario: Lifecycle notifications
- **WHEN** a run is invoked, and again when it completes
- **THEN** the corresponding lifecycle events fire so hooks and renderers can react
