## Purpose

Coordinates multi-step and multi-actor work: a task list for tracking progress,
parallel sub-agents for subtasks, and ask-the-user for blocking decisions — so
the agent can plan, delegate, and clarify within one run.

## Requirements

### Requirement: Task list for progress tracking
The todo write tool SHALL accept a full list of tasks, each with content, a
status among pending, in_progress, and completed, and a priority among high,
medium, and low, and SHALL replace the current list wholesale so the model keeps
the list authoritative.

#### Scenario: List is replaced wholesale
- **WHEN** todo_write is called with a full task list
- **THEN** the previous list is replaced and the new one is rendered for context

#### Scenario: Clearing the list
- **WHEN** todo_write is called with an empty list
- **THEN** the task list is cleared

### Requirement: Parallel sub-agents
The agent tool SHALL spawn a single sub-agent from a prompt, or fan out a list of
subtasks concurrently, capping the parallel workers so one call cannot saturate
the API, and SHALL return each sub-agent's answer in input order.

#### Scenario: Single sub-agent
- **WHEN** the agent tool is given one prompt
- **THEN** a sub-agent runs it and its final answer is returned

#### Scenario: Parallel fan-out preserves order
- **WHEN** the agent tool is given a list of subtasks
- **THEN** they run concurrently and answers come back in the input order

#### Scenario: A failing sub-agent does not abort the rest
- **WHEN** one subtask raises
- **THEN** its failure is captured in its slot and the other subtasks still complete

### Requirement: Ask the user
The ask-user tool SHALL surface a question to the operator and return the chosen
answer, blocking the loop until a response arrives.

#### Scenario: Question blocks for an answer
- **WHEN** the model needs a decision it cannot make itself
- **THEN** the question is presented and the loop waits on the answer
