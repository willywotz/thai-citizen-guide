# agent-proxy Refactor Design (Round 2)

**Date:** 2026-06-23
**Goals:** Correctness in the hot path, characterization coverage, request-path performance

## Context

`agent-proxy` is a small Go HTTP reverse proxy (~403 lines across `main.go`, `handler.go`,
`store.go`, `util.go`, plus thin tests). It receives requests at `/agent-proxy/{uuid}`, looks up
the target agency in PostgreSQL, forwards the request with injected API headers, logs the
connection, and increments a call counter. It traces with OpenTelemetry over OTLP/gRPC.

The 2026-06-09 refactor (file split, testable `handler` struct, store extraction, bug fixes)
is **complete**. This round addresses what that refactor explicitly deferred — panics and
swallowed errors in the request path, thin tests, and per-request work that should be cached —
following "make it work → make it right → make it fast".

## Current State (measured)

| File | Lines | Status |
|------|------:|--------|
| `main.go` | 89 | Done. Startup wiring, `initTracer`, `mustPanic`, `/health`, ListenAndServe error handled. |
| `handler.go` | 167 | Done structurally. Package-level regexps, `handler` struct, `httpClient` with 180s timeout. |
| `store.go` | 31 | Done. `agency`, `getAgency`, `insertConnectionLog`, `incrementTotalCalls`. |
| `util.go` | 54 | Done. `uuidV7`/`newUUIDv7`/`formatUUID`/`now`. Dead `GetCurlCommand` removed. |
| `handler_test.go` | 29 | Thin — two `StatusBadRequest` error paths only. |
| `store_test.go` | 33 | Thin — `getAgency` not-found, skips without `DATABASE_URL`. |

go 1.26.2 · pgx/v5 v5.9.2 (pgxpool) · OpenTelemetry v1.43.0 (otel, sdk, trace, otlptracegrpc).

### Already done (do NOT re-spec)

- File split into `main.go` / `handler.go` / `store.go` / `util.go`.
- `handler` struct with injected `pool` + `tracer`; constructible in tests.
- `pathRegexp` / `uuidRegexp` hoisted to package-level vars.
- `X-Forwarded-*` header deletion collects keys first, then deletes (no map mutation during range).
- Response double-buffer collapsed to `io.Copy(&responseBody, …)` then `io.Copy(w, bytes.NewReader(…))`.
- Dead code removed (`GetCurlCommand`, `var _ = now()`).
- Beyond prior spec, already present: `errors.Is(err, pgx.ErrNoRows)`, `NewRequestWithContext` error
  checked, `httpClient` with `Timeout: 180s`, ListenAndServe error handled, total_calls incremented
  only on success.

### Outstanding (this spec)

**WORK (correctness):**
1. `uuidV7` panics on `rand.Read` failure — in the connection-log insert path, killing the process
   on a transient entropy error.
2. `now()` calls `time.LoadLocation("Asia/Bangkok")` on every connection-log insert and panics if
   tzdata is missing — disk/cache lookup plus panic risk in the hot path.
3. `addConnectionLog` errors are swallowed at all three call sites (`_ = h.addConnectionLog(...)`),
   so audit-log write failures are invisible.
4. Request/response body `io.Copy` errors are discarded (`_, _ = io.Copy(...)`), so a truncated
   upstream read is forwarded silently as success.

**FAST (performance):**
5. `getAgency` hits Postgres on **every** request; agency config changes rarely.
6. Response body is fully buffered into memory (`responseBody`) before being written to the client,
   adding latency and memory for large answers.
7. `httpClient` uses default transport pooling — no `MaxIdleConns` / `MaxConnsPerHost` tuning for a
   proxy under load.
8. Full request and response bodies are attached verbatim to OTel span attributes — unbounded
   payload duplicated into trace export.

**TEST (precedes refactors):** characterization tests pinning the successful proxy flow, header
injection, and store success/not-found before any behavior change.

## Target structure

No new files. Same four-file layout; one new file `cache.go` for the agency cache.

```
agent-proxy/
  main.go      // startup; load tz once into a package var; build tuned http.Transport
  handler.go   // ServeHTTP: cache lookup, streaming copy, bounded span bodies, propagated errors
  store.go     // unchanged queries; getAgency still the source of truth behind the cache
  cache.go     // agencyCache: TTL + invalidation around getAgency
  util.go      // uuidV7 returns (string, error); now() reads cached *time.Location
  *_test.go    // characterization tests + cache unit tests
```

## WORK — make it right

- **`uuidV7` returns an error.** Change `func uuidV7() string` → `func uuidV7() (string, error)`;
  propagate `newUUIDv7`'s error instead of `panic`. `insertConnectionLog` returns the error up
  through `addConnectionLog`.
- **Cache the location at init.** Load `time.LoadLocation("Asia/Bangkok")` once into a package var
  in `util.go`'s `init()`; `now()` reads it. Fall back to `time.UTC` with a logged warning if tzdata
  is missing rather than panicking per request.
- **Log audit-write failures.** `addConnectionLog` already returns its error and logs internally;
  keep the `slog.Error` and additionally record it on the span. Call sites stay `_ =` (best-effort
  by design) but the failure is now observable in logs and traces — document as intentional.
- **Surface body-copy errors.** Capture the error from request and response `io.Copy`; on response
  read error, set span status to error and log. The bytes already written to the client cannot be
  unsent, so this is observability, not a contract change.

## RIGHT — outstanding structure

Structure from the prior spec is complete. The only new structural unit is `cache.go` (below);
no further file moves.

## FAST — make it fast

- **Agency cache (`cache.go`).** `agencyCache` wraps `getAgency` with a `sync.RWMutex`-guarded map
  keyed by agency ID, each entry carrying `value agency` and `expiresAt time.Time`. TTL configurable
  via `AGENCY_CACHE_TTL` (default 60s). `handler` gains a `cache *agencyCache` field; `ServeHTTP`
  calls `h.cache.get(ctx, agencyID)` instead of `getAgency` directly. Expose `invalidate(id)` for
  future cache-busting. `pgx.ErrNoRows` is NOT cached (avoids pinning a 404 after an agency goes
  active).
- **Stream the response.** Replace the buffer-then-write pair with a single `io.Copy(w, resp.Body)`
  to stream to the client. To still record `proxy.response_body` and build the connection-log
  `detail`, wrap the writer with an `io.MultiWriter` into a **bounded** buffer (cap at
  `maxSpanBodyBytes`) so the trace/log capture is capped while the client gets the full stream.
- **Tune the transport.** Build `httpClient` over a configured `*http.Transport`:
  `MaxIdleConns: 100`, `MaxIdleConnsPerHost: 100`, `MaxConnsPerHost: 0` (unlimited), keep
  `Timeout: 180s`.
- **Truncate span bodies.** Introduce `const maxSpanBodyBytes = 8 << 10` (8 KiB). A `truncate(s)`
  helper caps `proxy.body` and `proxy.response_body` span attributes, appending `…(truncated)`.

## Behavior Changes

1. **No panic on entropy failure.** A failing `rand.Read` now produces a logged error and a failed
   connection-log insert instead of crashing the process. The proxied response to the client is
   unaffected (logging is best-effort).
2. **No panic on missing tzdata.** Missing `Asia/Bangkok` data falls back to UTC with a startup
   warning instead of panicking per request. Timestamps shift to UTC only in the (mis)configured
   no-tzdata case; the deployed image ships tzdata, so production behavior is unchanged.
3. **Agency lookups are cached for ≤TTL.** A config change to an agency takes up to `AGENCY_CACHE_TTL`
   (default 60s) to take effect. Deactivation/404 is never cached. This is a visible-latency change
   to config propagation; documented and tunable.
4. **Span/log bodies are truncated at 8 KiB.** `proxy.body` and `proxy.response_body` attributes and
   the connection-log `detail` answer are capped. The proxied client response is byte-for-byte
   unchanged.
5. **Audit and body-copy errors are now logged/traced.** Previously silent failures become
   observable. No HTTP-contract change.

The `/agent-proxy/{uuid}` HTTP contract (method passthrough, header injection, status/headers/body
forwarding, `X-Forwarded-*` stripping) is otherwise unchanged.

## Testing

Characterization tests land **before** any refactor and must pass against current code:

- `handler_test.go` — successful proxy flow against an `httptest.NewServer` upstream: assert
  forwarded method, that injected `apiHeaders` reach the upstream, that `X-Forwarded-*` are stripped,
  and that the upstream status/headers/body are returned verbatim. Construct `handler` with a noop
  tracer; inject a fake/stub agency source so no DB is needed.
- Keep `TestServeHTTP_MissingID` / `TestServeHTTP_InvalidUUIDFormat`.
- `store_test.go` — keep `TestGetAgency_NotFound`; add a success case guarded by `DATABASE_URL`.
- `cache_test.go` (new) — hit caches and returns same value within TTL; miss re-queries after expiry;
  `invalidate` forces re-query; `ErrNoRows` is not cached.

Run via `rtk go test ./...` (skips DB tests without `DATABASE_URL`), `gofmt -w`, and
`golangci-lint run --allow-parallel-runners`.
