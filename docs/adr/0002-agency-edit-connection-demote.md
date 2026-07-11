# 0002 — Agency detail "Edit" tab: editing connection config demotes a live agency to draft

Status: Accepted — 2026-07-11

## Context

The agency detail page (`AgencyDetailPage.tsx`) had five tabs. Two of them
(**การเชื่อมต่อ / Connection** and **Routing**) were already inline editors with their
own save buttons, while the identity fields (name, short name, logo, color,
description) were editable **only** through the multi-step setup **wizard**
(`/agencies/{id}/setup`, `AgencyWizardPage`). Editing was therefore split across two
mental models and one common surface — general info — had no home on the detail page.

We consolidated editing into a single **แก้ไข (Edit)** tab with three per-section-save
groups (General / Connection / Routing), replacing the separate Connection and Routing
tabs.

Making connection config editable inline collides with the **conformance battery**: the
5-check gate (`responds`, `non_empty`, `thai_text`, `concurrency_3`, `garbage_input`)
that an agency must pass before `draft → active`. That report is stored on the agency and
was proven against a *specific* endpoint URL, protocol, headers, and payload. Editing any
of those inline makes the stored `conformance_report` a lie: the live agency is now
serving traffic under a configuration that was never validated.

The lifecycle tables (`lifecycle.ts` / `agency_lifecycle.py`) also **forbid any transition
back to `draft`** — `draft` is a one-way origin state — so there is no user-facing path to
"un-validate" an agency.

## Decision

**Editing any connection field of an `active` or `maintenance` agency demotes it to
`draft` and clears its `conformance_report`, atomically, in the backend.**

- **Trigger**: any change to a connection-identity field — `connection_type`,
  `endpoint_url`, `api_headers`, `expected_payload`, `mcp_tool_name`. General and Routing
  edits never demote.
- **Scope**: only `active` and `maintenance` demote. `disabled` stays `disabled` (already
  out of rotation, disabled deliberately); `draft` is a no-op. Conformance is cleared only
  together with the demotion (i.e. active/maintenance only).
- **Mechanism**: `PATCH /agencies/{id}` compares the incoming connection fields against the
  stored agency *before* applying the update. If any differ and status ∈ {active,
  maintenance}, it forces `status="draft"` and clears `conformance_report` in the same
  save. This is a **system reset**, so it deliberately bypasses the user-facing
  `is_legal_transition` guard rather than exposing a general `→ draft` transition anywhere.
- **Consent**: the frontend Connection section detects the same field diff and shows a
  **confirm dialog** before saving on a non-draft agency ("this moves the agency back to
  draft — continue?"), so demotion is never a surprise. Backend remains authoritative.
- **Connection type is editable** inline (API/MCP/A2A toggle, like the wizard); a type
  change is just the strongest case of the trigger above.

The Edit tab is gated on `!isReadOnly` (admin + agency_owner see it; auditor/viewer don't);
backend ReBAC (`agency:edit`) still limits `agency_owner` to their own agencies.

## Alternatives considered

- **Save + warn, no status change.** Frictionless, but leaves a live agency running an
  unvalidated configuration with only a soft warning. Rejected — conformance integrity is
  the point of the battery.
- **Demote only on `connection_type` change.** Cleaner line, but an endpoint-URL or
  payload change equally invalidates the tested configuration. Rejected in favor of the
  full connection-field set.
- **Add `active → draft` to the legal-transition tables** and have the frontend fire a
  second status call. Exposes a general "back to draft" transition that could be misused
  elsewhere, and isn't atomic. Rejected in favor of the backend system-reset.
- **Silent demotion (no confirm).** Simplest, but an admin tweaking a header would pull
  their agency offline with no opt-in. Rejected.

## Consequences

- Editing connection config on a live agency **pulls it out of rotation** until it is
  re-tested and re-activated through the wizard's test/activate gate. This is deliberate
  friction protecting answer quality.
- The backend PATCH now has a lifecycle side effect keyed off a field diff — a subtle
  coupling. Any future field added to the "connection identity" set must be added to the
  demote comparison, or it will silently skip re-validation.
- `disabled → active` remains a direct transition with no conformance re-check, so a
  disabled agency whose connection was edited (no demotion) can return to active with a
  now-stale report. Accepted: disabled is an explicit admin state and re-enabling is an
  explicit admin act.
- General and Routing edits stay lifecycle-neutral; only the Connection section carries the
  demote semantics.
