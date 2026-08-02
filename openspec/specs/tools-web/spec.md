## Purpose

Brings external information into the loop: web search with provider fallbacks,
web fetch that converts pages to markdown, and an optional Playwright-driven
browser — so research tasks stay offline-capable without the browser installed.

## Requirements

### Requirement: Web search with fallback providers
The web search tool SHALL run a query with a configurable result count
(default 5) and SHALL fall back through a chain of providers until one succeeds,
aggregating errors if all fail.

#### Scenario: Primary provider returns results
- **WHEN** the primary search provider succeeds
- **THEN** results are returned as numbered titles, urls, and snippets

#### Scenario: Fallback chain engages
- **WHEN** the primary provider fails
- **THEN** the next configured provider is tried in order

#### Scenario: All providers fail
- **WHEN** every provider in the chain fails
- **THEN** an error result aggregates the failures

### Requirement: Web fetch converts pages to markdown
The web fetch tool SHALL fetch a URL and return its content as markdown,
rejecting non-http(s) schemes, honoring a max-character limit (default 20,000)
with a truncation note, and reporting a fetch failure as an error.

#### Scenario: HTML page becomes markdown
- **WHEN** a fetched response is HTML
- **THEN** it is converted to markdown before returning

#### Scenario: Non-http scheme is rejected
- **WHEN** the URL scheme is not http or https
- **THEN** an error result names the unsupported scheme

#### Scenario: Oversized content is truncated
- **WHEN** fetched text exceeds the max-character limit
- **THEN** it is truncated with a note stating how many characters were dropped

### Requirement: Browser is optional
The web browser tool SHALL require Playwright and SHALL be absent when Playwright
is unavailable, while search and fetch keep working without it.

#### Scenario: Browser present when Playwright is installed
- **WHEN** Playwright is available
- **THEN** the browser tool is registered

#### Scenario: Search and fetch work without Playwright
- **WHEN** Playwright is not installed
- **THEN** web search and fetch still function
