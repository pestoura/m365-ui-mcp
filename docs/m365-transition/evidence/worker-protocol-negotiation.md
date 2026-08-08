# CORE-029 — Worker protocol version negotiation

Status: **IMPLEMENTED_AWAITING_GATES**

## Objective

Make control-plane/worker protocol compatibility an explicit runtime fact rather than an assumption derived from package versions or shared constants.

## Negotiation model

The worker starts fail closed:

```text
compatible = false
negotiated_version = null
```

`GET /protocol` exposes only bounded protocol metadata. `POST /protocol/negotiate` accepts a bounded list of numeric dotted versions supported by the private control-plane peer and selects the newest mutually supported version.

No common version produces `compatible=false` and clears any previously negotiated version. A later incompatible re-negotiation therefore revokes protocol readiness rather than retaining stale compatibility.

## Readiness binding

The default `protocol_compatible` readiness provider now reads the process-local `ProtocolNegotiator.compatible` state. The signal becomes true only after a successful explicit handshake.

This does not bypass any other readiness requirement. Browser ownership, profile viability, authentication, UIContract attestation, broker viability and profile serialization remain independent mandatory signals.

## Security boundary

The handshake accepts protocol-version metadata only. It contains no account, tenant, browser, cookie, token, URL, selector, header or storage-state content.

The negotiation route is private with the existing worker network topology; no host port is published.

## Acceptance coverage

Tests prove:

- initial compatibility is false;
- incompatible peers remain fail closed;
- compatible peers negotiate version `1`;
- explicit reset clears compatibility;
- a successful handshake promotes only the protocol readiness signal;
- an incompatible re-negotiation revokes readiness;
- extra or malformed handshake fields are rejected;
- protocol status contains only bounded metadata.

CORE-030 remains responsible for the expanded sanitized worker error taxonomy. Outlook remains `RESERVED`.
