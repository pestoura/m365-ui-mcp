# Threat model

## Assets
Professional browser session (persistent profile), Planner Premium data, control-plane state,
operational evidence.

## Trust boundaries
1. ChatGPT / Cloudflare Portal -> control plane (untrusted caller).
2. Control plane -> browser worker (private network only).
3. Browser worker -> Planner Premium UI (untrusted rendered content).

## Threats and mitigations
| ID | Threat | Mitigation |
| --- | --- | --- |
| T-1 | Credential exfiltration | No passwords/cookies/tokens in state, logs or repo; persistent profile is the auth mechanism |
| T-2 | Prompt injection via rendered Planner content | UI-derived data is `trust_level=untrusted_ui_derived`; no mutations in 0.1.0 |
| T-3 | Unintended mutations | Policy denies every non-read tool; worker exposes no mutating HTTP methods (test-enforced) |
| T-4 | Conditional Access bypass pressure | `BLOCKER_CONDITIONAL_ACCESS` fail-closed; enrolment forbidden |
| T-5 | UI drift causing wrong reads | Versioned UIContract, `UI_DRIFT`, `UI_CONTRACT_UNATTESTED` |
| T-6 | Container escape / privilege escalation | non-root, `no-new-privileges`, `cap_drop: ALL`, read-only rootfs, tmpfs |
| T-7 | Supply chain compromise | Trivy CRITICAL/HIGH gate, SBOM (CycloneDX) for both images, dependency and secret scanning |
| T-8 | Worker exposed publicly | Internal-only Docker network, no published worker port |
| T-9 | MFA phishing via chat channels | MFA approval only in Microsoft Authenticator; only sanitized metadata is surfaced |
