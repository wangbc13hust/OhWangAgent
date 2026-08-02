## Purpose

Centralizes local runtime configuration: permission rules persisted in
settings.json, and three-level feature flags that an operator can flip per
project without touching code.

## Requirements

### Requirement: Permission rules in settings.json
The system SHALL read allow, ask, and deny rule lists from .ohwang/settings.json,
where each entry is a tool name or glob pattern, and SHALL treat a missing or
malformed file as empty rules rather than failing.

#### Scenario: Rules are loaded
- **WHEN** settings.json defines allow, ask, or deny lists
- **THEN** the permission manager resolves against those rules

#### Scenario: Missing settings means empty rules
- **WHEN** no settings file exists or it is malformed
- **THEN** all rule lists are empty

### Requirement: Rules are editable and persisted
The system SHALL support adding a rule to a list, removing a rule from all lists,
and persisting the result back to settings.json, creating the file if needed.

#### Scenario: Rule is added and saved
- **WHEN** a rule is added to the allow list
- **THEN** the updated list is written back to settings.json

#### Scenario: Rule is removed everywhere
- **WHEN** a rule is removed
- **THEN** it is dropped from every list it appears in and the file is updated

### Requirement: Three-level feature flags
A feature flag SHALL resolve from the OHWANG_FEATURE_ environment variable for its
name, falling back to a per-project flags.json value, and finally to a built-in
default. Environment values SHALL be parsed case-insensitively so TRUE, True, and
YES all count as enabled.

#### Scenario: Environment variable wins
- **WHEN** OHWANG_FEATURE_<NAME> is set to a truthy value
- **THEN** the feature is enabled regardless of flags.json or the default

#### Scenario: Project file overrides the default
- **WHEN** no environment variable is set but flags.json enables the feature
- **THEN** the feature is enabled

#### Scenario: Built-in default applies otherwise
- **WHEN** neither the environment nor flags.json mention the feature
- **THEN** the built-in default decides
