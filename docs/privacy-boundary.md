# Privacy boundary

- Personal and professional browsing are separated: a dedicated, isolated Chromium profile directory
  is used exclusively for Planner work.
- The personal machine is never enrolled or managed.
- User identifiers, e-mail addresses, JWTs and bearer tokens are redacted from logs and tool output
  by `planner_mcp.redaction`.
- Only sanitized account context is exposed (`tenant_display`, `account_kind`, `profile`,
  `device_enrolment`), never the raw identity.
- No Planner content is persisted outside the state database, and 0.1.0 stores no Planner content.
