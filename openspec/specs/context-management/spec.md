## Purpose

Keeps the conversation inside the model's context window: exact token
estimation, window-derived compaction, oversized tool-result trimming, and
summarization — so long tasks do not die on prompt-too-long errors.

## Requirements

### Requirement: Token estimation is exact when possible
The system SHALL estimate token counts with a tokenizer when available and fall
back to heuristics otherwise. Heuristics SHALL treat CJK text as roughly one
token per character and other text as roughly one token per four characters.

#### Scenario: Exact tokenizer used when available
- **WHEN** the tokenizer is available for the model
- **THEN** text and message token estimates come from the tokenizer

#### Scenario: CJK heuristic fallback
- **WHEN** the tokenizer is unavailable and the text contains CJK characters
- **THEN** the estimate is approximately one token per character

### Requirement: Compaction threshold derives from the context window
The system SHALL derive a compaction threshold from the model's context window,
reserving output and buffer headroom, and SHALL floor the threshold at 4,000
tokens, using a default of 100,000 when no window is known.

#### Scenario: Window-derived threshold
- **WHEN** a model's context window is known
- **THEN** the threshold is the window minus the reserved output and buffer, floored at 4,000 tokens

#### Scenario: Unknown window default
- **WHEN** no context window is configured
- **THEN** the threshold defaults to 100,000 tokens

### Requirement: Compaction triggers on size and keeps recent messages
The system SHALL trigger compaction when the estimated token count exceeds the
threshold and the message count is greater than 8. Compaction SHALL summarize
older messages and keep the most recent 6 verbatim.

#### Scenario: Trigger condition met
- **WHEN** estimated tokens exceed the threshold and there are more than 8 messages
- **THEN** the conversation is compacted before the next model call

#### Scenario: Recent messages preserved
- **WHEN** a conversation is compacted
- **THEN** the most recent 6 messages remain verbatim

### Requirement: Summarization failures trip a circuit breaker
If summarization fails repeatedly, the system SHALL give up summarizing and
hard-trim older messages instead, so the conversation can still advance.

#### Scenario: Repeated failures fall back to hard trim
- **WHEN** summarization has failed 3 consecutive times
- **THEN** older messages are dropped and only the recent span is kept

### Requirement: Session summaries support resumption
The system SHALL be able to summarize a conversation into a terse brief for later
resumption, bounded in length and token budget, and SHALL fail silently on error.

#### Scenario: Summary produced for resume
- **WHEN** a session is saved with summarization enabled
- **THEN** a brief of the conversation is produced and stored with the session

#### Scenario: Summary failure is silent
- **WHEN** summarization fails
- **THEN** the save proceeds without a summary and no error is surfaced
