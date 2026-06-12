## 1. Implementation

- [x] 1.1 Thread quota planner repository access into live proxy selection.
- [x] 1.2 Honor all persisted routing strategy values in the proxy service.
- [x] 1.3 Scope `single_account` routing to the configured account ID.
- [x] 1.4 Persist and expose API-key `traffic_class`.
- [x] 1.5 Route opportunistic API keys through opportunistic account selection.
- [x] 1.6 Keep quota-planner background scheduling disabled by default.

## 2. Verification

- [x] 2.1 Add regression coverage for proxy strategy normalization, single-account scoping, and API-key traffic-class routing.
- [x] 2.2 Run focused backend tests for proxy routing and API-key service behavior.
- [x] 2.3 Run type, lint, and OpenSpec validation gates.
