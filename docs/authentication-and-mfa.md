# Authentication and MFA

## States
`UNKNOWN, READY, AUTH_REQUIRED, MFA_REQUIRED, WAITING_FOR_MFA, AUTHENTICATED, SESSION_EXPIRED, AUTH_FAILED`

Transitions are guarded by `planner_mcp.auth.AuthContext`; illegal transitions raise.

## Number matching
Microsoft Authenticator number matching is **detected**, never automated. The MCP surfaces only
sanitized metadata:

| Field | Meaning |
| --- | --- |
| `mfa_number` | 2-digit number to select in Authenticator |
| `operation_id` | Correlation id for the auth attempt |
| `service` | Identity service (e.g. `microsoft-entra-id`) |
| `description` | Sanitized description of the sign-in |
| `expires_at` | Challenge expiry |
| `approval_channel` | Always `microsoft_authenticator` |

Approval happens **only** inside Microsoft Authenticator. It is never performed in Telegram, Hermes,
ChatGPT or any other channel.

## Conditional Access
If the sign-in requires a compliant or managed device, the worker raises
`BLOCKER_CONDITIONAL_ACCESS` and stops. No enrolment, no bypass, no spoofing.
