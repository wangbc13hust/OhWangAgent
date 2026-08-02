## Purpose

Provides a pluggable multi-provider model layer that presents one unified
streaming event format to the agent loop, so anthropic, openai, and four
OpenAI-compatible Chinese providers behave identically to the caller.

## Requirements

### Requirement: Unified streaming event stream
The provider SHALL stream events to the loop as text events, tool-use events,
and a final stop signal.

#### Scenario: Text streaming
- **WHEN** the model produces text
- **THEN** the provider yields text events carrying incremental text

#### Scenario: Tool use
- **WHEN** the model decides to call a tool
- **THEN** the provider yields a tool-use event carrying an id, name, and JSON input

### Requirement: Provider presets carry defaults
The system SHALL ship presets for anthropic, openai, zhipu, deepseek, kimi, and
qwen, each defining an API-key environment variable, a default model, a base URL
(or native default endpoint), and a context window.

#### Scenario: Defaults resolve
- **WHEN** a provider is selected without an explicit model or API key
- **THEN** the preset's default model is used and the API key is read from the preset's environment variable

#### Scenario: Explicit overrides win
- **WHEN** the user passes an explicit model, base URL, or context window
- **THEN** those values override the preset defaults

### Requirement: OpenAI-compatible routing
Every provider other than anthropic SHALL speak the OpenAI-compatible function
calling protocol and SHALL translate the unified tool schema into OpenAI function
definitions and back.

#### Scenario: Tool schema translation
- **WHEN** a tool spec is sent to an OpenAI-compatible provider
- **THEN** it is translated into a function definition with name, description, and parameters

#### Scenario: Tool result round-trip
- **WHEN** a tool result is appended to the conversation
- **THEN** it is translated into an OpenAI tool message addressed to the matching call id

### Requirement: Native Anthropic passthrough with prompt caching
The anthropic provider SHALL pass messages through in native Anthropic
content-block form and SHALL enable prompt caching by default, placing a cache
breakpoint on the system block and on the final message.

#### Scenario: Prompt caching on by default
- **WHEN** using the anthropic provider without disabling caching
- **THEN** the system block and the final message carry ephemeral cache-control markers

#### Scenario: Caching can be disabled
- **WHEN** the DISABLE_PROMPT_CACHING environment variable is set
- **THEN** no cache-control markers are attached

### Requirement: Usage accounting is thread-safe
The provider SHALL accumulate prompt tokens, completion tokens, and call counts
under a lock so that parallel sub-agents sharing one provider instance cannot
corrupt the counters.

#### Scenario: Concurrent calls accumulate correctly
- **WHEN** multiple sub-agents call a shared provider concurrently
- **THEN** the reported usage equals the sum of all calls' tokens

### Requirement: Provider errors are normalized
A failed API request SHALL be raised as a single normalized error that names the
provider and model.

#### Scenario: API failure surfaces provider context
- **WHEN** an API request fails
- **THEN** the raised error names the provider and model so the cause is diagnosable
