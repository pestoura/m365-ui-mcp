# Power BI UI MCP — Authentication and MFA

## 1. Security objective

Support normal Microsoft 365 interactive authentication for a dedicated Power BI browser worker without attempting to bypass Conditional Access, MFA, device requirements or tenant policy.

MFA remains explicitly human-in-the-loop.

## 2. Session topology

```text
powerbi-browser-worker
        |
        +-- dedicated Chromium profile
        +-- dedicated persistent state
        +-- local secret resolver
        +-- MFA challenge detector
        +-- Hermes Telegram notifier
        +-- auth state machine
```

The Power BI profile must not share cookies/session storage with Planner or Outlook workers.

## 3. Login sequence

```text
SESSION_START
   |
   v
navigate Power BI target URL
   |
   +-- existing session valid? -- yes --> AUTHENTICATED
   |
   no
   v
Microsoft username screen
   |
resolve username locally
   v
Microsoft password screen
   |
resolve password locally
   v
MFA challenge
   |
   +-- number matching --> extract displayed number
   |                      send Telegram notification
   |                      state=MFA_PENDING
   |                      user confirms in Authenticator
   |                      observe navigation/success
   |
   +-- unsupported/ambiguous challenge --> BLOCKED_AUTH
   v
AUTHENTICATED
   |
persist bounded browser session state
   v
continue requested Power BI operation
```

## 4. Telegram notification

Expected content is minimal and contains no password, token, cookie or session identifier.

Example:

```text
Power BI / Microsoft MFA
Introduz o número 42 no Microsoft Authenticator.
```

Optional metadata may include a non-sensitive worker/application label and challenge timestamp.

The worker must not accept an MFA approval response through Telegram as a substitute for Microsoft Authenticator. Telegram is notification only.

## 5. Credential handling

Credentials are resolved inside the trusted runtime from an approved local secret store.

Forbidden paths:

- MCP tool argument containing password;
- ChatGPT prompt containing password;
- repository files containing credentials;
- environment variable names/values that violate the shared M365 secret policy;
- screenshots containing secrets without redaction;
- logs containing usernames/passwords/tokens/cookies;
- returning authentication material to the MCP control plane.

The control plane should receive only sanitized auth state, for example:

```json
{
  "application": "powerbi",
  "state": "MFA_PENDING",
  "challenge_kind": "NUMBER_MATCHING",
  "notification_sent": true
}
```

The actual MFA number may be delivered directly by the notifier path and need not be exposed to the LLM unless explicitly required by the implementation.

## 6. Session persistence

A successful session may persist browser state to reduce unnecessary MFA prompts, subject to Microsoft session policy and local security controls.

The implementation must distinguish:

```text
SESSION_VALID
SESSION_EXPIRED
REAUTH_REQUIRED
MFA_REQUIRED
CONDITIONAL_ACCESS_BLOCKED
DEVICE_COMPLIANCE_REQUIRED
AUTH_STATE_AMBIGUOUS
```

Expired state triggers normal authentication. It must never trigger attempts to bypass Microsoft controls.

## 7. Fail-closed conditions

Stop and report a blocker when:

- Conditional Access denies access;
- a managed/compliant device is required and unavailable;
- CAPTCHA or an unsupported challenge prevents deterministic progression;
- the MFA number cannot be extracted reliably;
- the Telegram notification path is unavailable and the configured policy requires it;
- the user declines/times out the MFA challenge;
- the post-MFA state cannot be proven;
- Microsoft reports suspicious activity or requires account recovery.

## 8. Acceptance evidence

Authentication acceptance must prove, without storing secrets:

1. dedicated worker started;
2. target URL reached;
3. authentication state classified;
4. MFA challenge detected when present;
5. notification path executed;
6. successful post-MFA transition observed;
7. target Power BI report loaded;
8. session state persisted according to policy;
9. subsequent session reuse works or cleanly reauthenticates.
