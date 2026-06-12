## ADDED Requirements

### Requirement: API keys expose traffic class

API key create, update, list, and read responses MUST support a `traffic_class` field with values `foreground` and `opportunistic`. The default MUST be `foreground`. Invalid values MUST be rejected before persistence.

#### Scenario: Create opportunistic API key

- **WHEN** an admin creates an API key with `trafficClass = "opportunistic"`
- **THEN** the key is persisted with opportunistic traffic class
- **AND** subsequent API-key responses include `trafficClass = "opportunistic"`

#### Scenario: Foreground remains default

- **WHEN** an admin creates an API key without `trafficClass`
- **THEN** the key is persisted and returned with `trafficClass = "foreground"`
