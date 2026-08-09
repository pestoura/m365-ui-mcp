# M365 change records

This directory is the canonical JDS-002 ledger for changes discovered after a candidate, accepted wave or product release baseline exists.

Create `CHG-M365-<NNN>.yaml` when validation, live UI attestation, Microsoft UI drift, a security review, compatibility change or production observation requires a product change.

Use the canonical JDS-002 classes: `HOTFIX`, `BUGFIX`, `HARDENING`, `IMPROVEMENT`, `COMPATIBILITY`, `SECURITY_FIX`, `BREAKING_CHANGE`, `DOC_ONLY`.

A change record does not by itself promote an Outlook capability to the public MCP registry or to live support. Those promotions remain evidence-gated by the M365 product contracts.

Historical waves are not retroactively rewritten into change records. JDS-002 applies from this adoption baseline forward.
