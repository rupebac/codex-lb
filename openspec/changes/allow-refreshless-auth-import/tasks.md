## 1. Import And Proxy Behavior

- [x] 1.1 Preserve empty imported refresh-token material and missing-token status.
- [x] 1.2 Add a connectivity-only SOCKS5 proxy probe for refreshless/import-time proxy validation.
- [x] 1.3 Use connectivity-only proxy validation for `auth.json` import with proxy fields and avoid token rotation in that path.

## 2. Verification

- [x] 2.1 Add regression tests for import-with-proxy and proxy updates with empty refresh-token material.
- [x] 2.2 Run targeted tests and strict OpenSpec validation.
