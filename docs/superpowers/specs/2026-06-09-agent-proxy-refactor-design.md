# agent-proxy Refactor Design

**Date:** 2026-06-09  
**Goals:** Testability, code organisation, bug fixes

## Context

`agent-proxy` is a small Go HTTP reverse proxy (~220 lines across `main.go` + `util.go`). It receives requests at `/agent-proxy/{uuid}`, looks up the target agency in PostgreSQL, forwards the request with injected API headers, logs the connection, and increments a call counter. It uses OpenTelemetry tracing via Jaeger.

The current structure has all proxy logic as a large closure inside `main()`, regexps compiled on every request, a header-mutation-during-iteration bug, dead code, and no testable units.

## File Structure

```
agent-proxy/
  main.go      // startup only: DB pool, tracer init, route registration, ListenAndServe
  handler.go   // handler struct, ServeHTTP, addConnectionLog, package-level regexps
  store.go     // getAgency, insertConnectionLog, incrementTotalCalls
  util.go      // uuidV7, now (dead code removed)
```

## Handler

Package-level regexp vars (compiled once at startup):

```go
var (
    pathRegexp = regexp.MustCompile(`^/agent-proxy/([^/]+)`)
    uuidRegexp = regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
)
```

`handler` struct holds the two injected dependencies:

```go
type handler struct {
    pool   *pgxpool.Pool
    tracer trace.Tracer
}

func (h *handler) ServeHTTP(w http.ResponseWriter, r *http.Request)
func (h *handler) addConnectionLog(ctx context.Context, agencyID, status string, latency int64, detail, requestBody, responseBody string)
```

Registered in `main.go` as:

```go
http.Handle("/agent-proxy/", &handler{pool: pool, tracer: tracer})
```

## Store

Standalone functions, each owning one SQL query:

```go
type agency struct {
    endpointURL string
    apiHeaders  []map[string]string
}

func getAgency(ctx context.Context, pool *pgxpool.Pool, id string) (agency, error)
func insertConnectionLog(ctx context.Context, pool *pgxpool.Pool, agencyID, status string, latency int64, detail, requestBody, responseBody string) error
func incrementTotalCalls(ctx context.Context, pool *pgxpool.Pool, id string) error
```

No interface wrapping — YAGNI for a service this size. Testable directly against a real DB.

## Bug Fixes

1. **Regexp hoisting** — `pathRegexp` and `uuidRegexp` moved to package-level vars; no longer compiled on every request.
2. **Header-iteration bug** — `X-Forwarded-*` headers were deleted while ranging over the map (undefined behaviour). Fix: collect matching keys into a slice first, then delete in a separate loop.
3. **Double-buffer response** — response body was buffered into `responseBody`, `resp.Body` replaced with a new reader, then copied again. Fix: `io.Copy(w, &responseBody)` directly after the first copy.
4. **Dead code removed** — `GetCurlCommand` (never called) and `var _ = now()` both deleted from `util.go`.

## Testing

Tests in `handler_test.go` (`package main`). Can construct `handler{pool: testPool, tracer: noop}` directly. Integration tests use a real DB pool pointed at a test database.
