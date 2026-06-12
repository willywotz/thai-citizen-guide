# Health-based auto-transition of agency status

**Date:** 2026-06-12
**Status:** Approved

## Goal

Automatically switch an agency's lifecycle status based on its recent health:

- If the 24h **error rate is more than 50%**, an `active` agency switches to `maintenance`.
- If the 24h **error rate is lower than 50%**, a rule-set `maintenance` agency switches back to `active`.

## Rule

Error rate is derived from `ConnectionLog` over the trailing 24h:

```
error_rate = failures / checks * 100      # equivalently 100 - uptime_24h
```

A transition is applied only when **all** of the following hold:

- `checks >= 5` in the trailing 24h (avoid acting on noisy small samples).
- Status is `active` and `error_rate > 50` → switch to `maintenance` (strict `>`).
- Status is `maintenance` **and rule-set** and `error_rate < 50` → switch to `active` (strict `<`).

No change occurs when:

- `checks < 5`.
- `error_rate` is exactly `50`.
- Status is `draft`, `disabled`, or legacy `inactive`.
- Status is `maintenance` but was **set by a human** (not by this rule).

## Manual override protection

Only `maintenance` that the rule itself set may be auto-reactivated. This is tracked
with a new boolean field on `Agency`:

- `auto_maintenance: bool = False`

The rule sets `auto_maintenance = True` when it moves an agency into `maintenance`,
and clears it (`False`) when it moves the agency back to `active`.

Every **manual** status transition (the admin PATCH endpoint) sets
`auto_maintenance = False`, so a human deliberately putting an agency into
`maintenance` is never auto-reverted, and a human reactivation clears any stale flag.

## Components

### 1. Model — `app/models/agency.py`

Add `auto_maintenance = fields.BooleanField(default=False)`.

Migration: the production DB uses aerich, so add an aerich migration adding the column.
The SQLite in-memory test DB rebuilds from the model via `generate_schemas`, so tests
pick up the column automatically.

### 2. Health helper — `app/services/agency_health.py`

Add `async def error_window(agency_id) -> tuple[int, int]` returning `(checks, failures)`
over the trailing 24h, reusing the existing `_rows` helper. `embedded_health` is unchanged.

### 3. Reconciliation service — `app/services/agency_reconcile.py` (new)

`async def reconcile_statuses()`:

- Iterate agencies whose status is `active` or `maintenance`.
- Fetch `(checks, failures)` via `error_window`.
- Skip if `checks < 5`.
- Compute `error_rate`.
- `active` and `error_rate > 50` → set `status = maintenance`, `auto_maintenance = True`,
  `save(update_fields=["status", "auto_maintenance", "updated_at"])`.
- `maintenance` and `auto_maintenance` and `error_rate < 50` → set `status = active`,
  `auto_maintenance = False`, save the same fields.
- `print` each applied transition (matching the scheduler's existing logging style).

### 4. Scheduler hook — `app/scheduler.py`

Call `await reconcile_statuses()` at the end of `agency_chat_test`, after the
`asyncio.gather` of health checks, so reconciliation runs every
`HEALTH_CHECK_INTERVAL_MINUTES` on freshly written data.

### 5. Manual override guard — `app/routers/agencies.py`

In PATCH `/{agency_id}/status`, set `agency.auto_maintenance = False` and add it to
`update_fields`.

## Testing (TDD)

- `active` → `maintenance` when `error_rate > 50` and `checks >= 5`; sets `auto_maintenance=True`.
- No flip when `checks < 5`.
- No flip at exactly `50%`.
- Rule-set `maintenance` → `active` when `error_rate < 50`; clears `auto_maintenance`.
- Human-set `maintenance` (`auto_maintenance=False`) is **not** auto-reactivated.
- `draft` / `disabled` agencies are untouched.
- Manual PATCH transition clears `auto_maintenance`.

## Out of scope

- Configurable thresholds (50%, 5 checks) — hard-coded for now; can be lifted into
  `settings` later if needed.
- Notifications/alerts on transition.
- Changes to `disabled`/`draft` automation.
