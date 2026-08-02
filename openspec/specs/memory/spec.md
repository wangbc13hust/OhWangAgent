## Purpose

Gives the agent durable, project- and user-scoped memory: stored facts,
automatic extraction from conversations, and relevance-ranked recall into the
system context.

## Requirements

### Requirement: Layered fact storage
The system SHALL store facts in project and user layers under
.ohwang/memory/facts.json relative to the project and the user home respectively.
The user layer SHALL be created lazily on first write.

#### Scenario: Project facts persist under the project
- **WHEN** a fact is stored at project scope
- **THEN** it is persisted under the project's .ohwang/memory/facts.json

#### Scenario: User layer is created lazily
- **WHEN** a user-scoped fact is written and the user layer does not exist yet
- **THEN** the directory is created on that first write

### Requirement: Typed facts with routing
Each fact SHALL carry a value, a list of tags, and a type among user, feedback,
project, and reference. Facts typed "user" SHALL route to the user layer when it
is enabled and SHALL fall back to the project layer when it is not, so the fact
is never dropped.

#### Scenario: User facts route to the global layer
- **WHEN** an extracted fact is typed "user" and the user layer is enabled
- **THEN** it is stored in the global memory layer

#### Scenario: Fallback when the user layer is disabled
- **WHEN** an extracted fact is typed "user" but the user layer is unavailable
- **THEN** it is stored in the project layer instead

### Requirement: Automatic extraction from conversations
The system SHALL extract facts automatically after the conversation has grown by
a threshold (default 20 messages), sending the most recent 30 messages to the
model. The extraction cursor SHALL persist across restarts and SHALL NOT advance
when extraction fails.

#### Scenario: Extraction triggers on growth
- **WHEN** the conversation has grown by at least 20 messages since the last extraction
- **THEN** the recent span is sent for extraction and the cursor advances on success

#### Scenario: Failed extraction retries next time
- **WHEN** extraction fails
- **THEN** the cursor does not advance and extraction is retried on a later run

### Requirement: Relevance-ranked recall
The system SHALL score memory facts against a query with whole-query hits in key,
tags, and value weighted higher than per-token hits, and SHALL rank results with
score descending and ties broken by insertion order.

#### Scenario: Multi-word and CJK queries
- **WHEN** a query contains multiple words or CJK characters
- **THEN** both whole-query and per-token matching apply so relevant facts surface

#### Scenario: Recall is capped
- **WHEN** memory is ranked into context
- **THEN** the number surfaced is capped, with ranked recall at 10 and context rendering at 30
