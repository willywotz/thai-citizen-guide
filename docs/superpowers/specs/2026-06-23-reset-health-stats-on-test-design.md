# Reset health stats on connection test

**Date:** 2026-06-23
**Status:** Approved (design)

## Problem

Agency health measures (`ล่ม`/down state, uptime, latency, auto-maintenance
error rate, history charts) are all computed from `ConnectionLog` rows over a
trailing time window. After an admin fixes a broken endpoint, the agency keeps
looking unhealthy because the window still contains the old failures, and an
auto-maintenance agency only recovers once the reconcile loop accumulates
≥5 fresh checks under the 50% threshold. There is no way to say "start
measuring from now."

## Goal

Let an admin reset an agency's health measurement baseline. The reset rides on
the existing **Test connection** action — each test click stamps a baseline so
that all subsequent measures only consider data from that point forward.

## Decisions

| Question | Decision |
|---|---|
| Mechanism | **Soft reset (baseline cutoff).** Keep `ConnectionLog` rows; store `stats_reset_at` on the agency. Measures ignore rows older than it. Reversible, auditable. |
| Trigger | **Reset on test only.** No separate button — clicking *Test connection* is the reset. Each test starts a fresh measurement window. |
| Status effect | **Reactivate if auto-set, gated on test success.** If `status==maintenance and auto_maintenance` *and the test passes*, flip to `active` and clear `auto_maintenance`. Manual maintenance untouched. |
| Scope | **All measures honor the cutoff** — `embedded_health` (ล่ม/uptime/latency), `error_window` (auto-maintenance), and `health_history` (charts). |

## Design

### 1. Data model

Add one nullable field to `Agency` (`backend/app/models/agency.py`):

```python
stats_reset_at = fields.DatetimeField(null=True)
```

`NULL` means "count all history" — existing agencies are unaffected. Add an
aerich migration in `backend/migrations/models/` adding the nullable column.

### 2. Measures honor the cutoff

Thread the cutoff through the three read paths in
`backend/app/services/agency_health.py`. Every caller already holds the agency
object, so the value is passed in — **no extra queries**.

```python
async def error_window(agency_id, reset_at=None) -> tuple[int, int]: ...
async def embedded_health(agency_id, reset_at=None) -> dict: ...
async def health_history(agency_id, window, reset_at=None) -> list[dict]: ...
```

Each clamps its window start:

```python
since = max(window_start, reset_at) if reset_at else window_start
```

Callers to update:
- `backend/app/routers/agencies/_utils.py:10` — pass `agency.stats_reset_at`.
- `backend/app/services/agency_reconcile.py:22` — pass `ag.stats_reset_at`.
- `backend/app/routers/agencies/lifecycle.py:108` — capture the `Agency.get`
  result and pass `agency.stats_reset_at` to `health_history`.

### 3. The test endpoint performs the reset

In `test_connection_endpoint` (`backend/app/routers/agencies/lifecycle.py:122`),
wrap the existing flow:

```
cutoff = now()
agency.stats_reset_at = cutoff
run test -> response
if response.success and agency.status == "maintenance" and agency.auto_maintenance:
    agency.status = "active"
    agency.auto_maintenance = False
    reactivated = True
await agency.save(update_fields=[...])
if reactivated: agency_directory.invalidate()
create ConnectionLog(...)   # created_at > cutoff, so this fresh result is in-window
```

Ordering guarantees: `cutoff = now()` is captured before the log is created,
and the comparison is `created_at >= cutoff`, so the just-written test result is
always included in the post-reset window. After a reset the in-window history is
exactly this one fresh result — "measure from this point."

Every test click resets, including failed tests. A failed test resets the
window (so the agency immediately reads as `ล่ม` from the single failed check)
but does **not** reactivate.

### 4. Frontend

No new control — the reset rides on the existing Test button. The agency page
already refetches health after a test, so the new baseline reflects
automatically. No frontend changes expected beyond confirming the existing
post-test refetch.

## Testing (TDD)

Backend:
- `error_window` / `embedded_health` / `health_history` exclude rows older than
  `reset_at`, and behave as before when `reset_at is None`.
- Test endpoint sets `stats_reset_at = now()` and the freshly created log is
  in-window.
- Successful test on an auto-set maintenance agency reactivates it
  (`status=active`, `auto_maintenance=False`) and invalidates the directory.
- Failed test does **not** reactivate, and leaves a single in-window failure
  (state reads `down`/`ล่ม`).
- Manual maintenance (`auto_maintenance=False`) is never reactivated by a test.

## Out of scope

- A separate "Reset stats" button (explicitly declined).
- Hard deletion / retention changes for `ConnectionLog`.
- Surfacing `stats_reset_at` in the UI (YAGNI; can follow later).
