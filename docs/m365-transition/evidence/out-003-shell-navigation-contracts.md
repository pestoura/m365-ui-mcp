# OUT-003 — Outlook shell/navigation contracts

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_002**

## Objective

Define the bounded semantic Outlook shell/navigation contract before locator discovery, without embedding a generic browser primitive or making a live-support claim.

## Contract vocabulary

The Outlook application now declares five closed shell targets:

- mail;
- calendar;
- people;
- To Do;
- settings.

Each target has a stable `outlook.shell.*` contract key, a semantic role and an explicit `UNVERIFIED_LIVE` evidence state.

## Deliberate separation from locator evidence

OUT-003 specifies *what* later discovery must identify. It does not specify CSS, XPath, URL, JavaScript, DOM commands or arbitrary browser actions. Locator strategies and UIContract attestation remain evidence-backed work in later Outlook discovery/capability phases.

The model refuses any OUT-003 contract that attempts to claim `ATTESTED` or another live state.

## Safety and dependency boundary

This work is stacked on OUT-002 and cannot merge before OUT-002 is merged and post-merge GREEN. Outlook remains `RESERVED` with zero public Tool Registry entries and zero browser operations.

## Acceptance coverage

Tests prove deterministic target order, namespace uniqueness, authenticated-shell requirement, `UNVERIFIED_LIVE` state, absence of generic browser/session primitives and continued zero Outlook execution exposure.
