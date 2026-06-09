# agent-proxy Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic `main.go` into focused files, extract a testable `handler` struct, pull DB queries into standalone store functions, and fix four bugs in the process.

**Architecture:** Everything stays in `package main` — no sub-packages. Four files: `main.go` (startup wiring), `handler.go` (handler struct + request lifecycle), `store.go` (three DB functions), `util.go` (uuid + time helpers). The `handler` struct takes `pool` and `tracer` as fields, making it directly constructible in tests.

**Tech Stack:** Go 1.26, pgx/v5, OpenTelemetry (Jaeger), net/http

> **Note:** Before writing any Go code, invoke the `/use-modern-go` skill as required by CLAUDE.md.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `agent-proxy/util.go` | Modify | Remove `GetCurlCommand` (dead) and `var _ = now()` |
| `agent-proxy/store.go` | Create | `agency` type, `getAgency`, `insertConnectionLog`, `incrementTotalCalls` |
| `agent-proxy/store_test.go` | Create | Integration test for `getAgency` (skips without `DATABASE_URL`) |
| `agent-proxy/handler.go` | Create | Package-level regexps, `handler` struct, `ServeHTTP`, `addConnectionLog` |
| `agent-proxy/handler_test.go` | Create | Unit tests for path parsing and UUID validation |
| `agent-proxy/main.go` | Modify | Strip to startup wiring only; wire `&handler{pool, tracer}` |

---

## Task 1: Clean up util.go

**Files:**
- Modify: `agent-proxy/util.go`

- [ ] **Step 1: Remove dead code from util.go**

Replace the entire file with:

```go
package main

import (
	"crypto/rand"
	"encoding/hex"
	"time"
)

func uuidV7() string {
	uuid, err := newUUIDv7()
	if err != nil {
		panic(err)
	}
	return formatUUID(uuid)
}

func newUUIDv7() ([16]byte, error) {
	var uuid [16]byte
	ms := uint64(time.Now().UnixMilli())
	uuid[0] = byte(ms >> 40)
	uuid[1] = byte(ms >> 32)
	uuid[2] = byte(ms >> 24)
	uuid[3] = byte(ms >> 16)
	uuid[4] = byte(ms >> 8)
	uuid[5] = byte(ms)
	if _, err := rand.Read(uuid[6:]); err != nil {
		return uuid, err
	}
	uuid[6] = (uuid[6] & 0x0f) | 0x70
	uuid[8] = (uuid[8] & 0x3f) | 0x80
	return uuid, nil
}

func formatUUID(uuid [16]byte) string {
	var buf [36]byte
	hex.Encode(buf[0:8], uuid[0:4])
	buf[8] = '-'
	hex.Encode(buf[9:13], uuid[4:6])
	buf[13] = '-'
	hex.Encode(buf[14:18], uuid[6:8])
	buf[18] = '-'
	hex.Encode(buf[19:23], uuid[8:10])
	buf[23] = '-'
	hex.Encode(buf[24:36], uuid[10:16])
	return string(buf[:])
}

func now() time.Time {
	loc, err := time.LoadLocation("Asia/Bangkok")
	if err != nil {
		panic(err)
	}
	return time.Now().In(loc)
}
```

Removed: `GetCurlCommand` (never called), `var _ = now()` (spurious side-effect), and unused imports (`bytes`, `fmt`, `io`, `net/http`, `strings`).

- [ ] **Step 2: Verify build**

```bash
cd agent-proxy && go build ./...
```

Expected: no output (clean build).

- [ ] **Step 3: Commit**

```bash
rtk git add agent-proxy/util.go
rtk git commit -m "refactor(agent-proxy): remove dead code from util.go"
```

---

## Task 2: Create store.go

**Files:**
- Create: `agent-proxy/store_test.go`
- Create: `agent-proxy/store.go`

- [ ] **Step 1: Write the failing test**

Create `agent-proxy/store_test.go`:

```go
package main

import (
	"context"
	"os"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("connect to test DB: %v", err)
	}
	t.Cleanup(pool.Close)
	return pool
}

func TestGetAgency_NotFound(t *testing.T) {
	pool := testPool(t)
	_, err := getAgency(context.Background(), pool, "00000000-0000-0000-0000-000000000000")
	if err != pgx.ErrNoRows {
		t.Fatalf("want pgx.ErrNoRows, got %v", err)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent-proxy && go test ./...
```

Expected: compile error — `undefined: getAgency`

- [ ] **Step 3: Create store.go**

Create `agent-proxy/store.go`:

```go
package main

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

type agency struct {
	endpointURL string
	apiHeaders  []map[string]string
}

func getAgency(ctx context.Context, pool *pgxpool.Pool, id string) (agency, error) {
	const q = "select endpoint_url, api_headers from agencies where id = $1 and status = 'active'"
	var a agency
	err := pool.QueryRow(ctx, q, id).Scan(&a.endpointURL, &a.apiHeaders)
	return a, err
}

func insertConnectionLog(ctx context.Context, pool *pgxpool.Pool, agencyID, status string, latency int64, detail, requestBody, responseBody string) error {
	const q = "insert into connection_logs (id, action, connection_type, status, latency_ms, detail, created_at, agency_id, request_body, response_body) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
	_, err := pool.Exec(ctx, q, uuidV7(), "proxy", "API", status, latency, detail, now(), agencyID, requestBody, responseBody)
	return err
}

func incrementTotalCalls(ctx context.Context, pool *pgxpool.Pool, id string) error {
	const q = "update agencies set total_calls = total_calls + 1 where id = $1"
	_, err := pool.Exec(ctx, q, id)
	return err
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent-proxy && go test ./...
```

Expected (no `DATABASE_URL` set):
```
--- SKIP: TestGetAgency_NotFound (0.00s)
    store_test.go:14: DATABASE_URL not set
PASS
ok  	github.com/willywotz/thai-citizen-guide/agent-proxy	0.001s
```

Expected (with `DATABASE_URL` set):
```
--- PASS: TestGetAgency_NotFound (0.01s)
PASS
ok  	github.com/willywotz/thai-citizen-guide/agent-proxy	0.012s
```

- [ ] **Step 5: Commit**

```bash
rtk git add agent-proxy/store.go agent-proxy/store_test.go
rtk git commit -m "refactor(agent-proxy): extract store functions into store.go"
```

---

## Task 3: Create handler.go

**Files:**
- Create: `agent-proxy/handler_test.go`
- Create: `agent-proxy/handler.go`

- [ ] **Step 1: Write the failing tests**

Create `agent-proxy/handler_test.go`:

```go
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"go.opentelemetry.io/otel/trace/noop"
)

func TestServeHTTP_MissingID(t *testing.T) {
	h := &handler{tracer: noop.NewTracerProvider().Tracer("")}
	req := httptest.NewRequest(http.MethodPost, "/agent-proxy/", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("want %d, got %d", http.StatusBadRequest, w.Code)
	}
}

func TestServeHTTP_InvalidUUIDFormat(t *testing.T) {
	h := &handler{tracer: noop.NewTracerProvider().Tracer("")}
	req := httptest.NewRequest(http.MethodPost, "/agent-proxy/not-a-uuid", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("want %d, got %d", http.StatusBadRequest, w.Code)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd agent-proxy && go test ./...
```

Expected: compile error — `undefined: handler`

- [ ] **Step 3: Create handler.go**

Create `agent-proxy/handler.go`:

```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"regexp"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

var (
	pathRegexp = regexp.MustCompile(`^/agent-proxy/([^/]+)`)
	uuidRegexp = regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
)

type handler struct {
	pool   *pgxpool.Pool
	tracer trace.Tracer
}

func (h *handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	ctx, span := h.tracer.Start(r.Context(), "Handle HTTP Request")
	defer span.End()

	m := pathRegexp.FindStringSubmatch(r.URL.Path)
	if len(m) < 2 {
		span.SetStatus(codes.Error, "missing id")
		http.Error(w, "Bad Request: missing id", http.StatusBadRequest)
		return
	}
	agencyID := m[1]

	if !uuidRegexp.MatchString(agencyID) {
		span.SetStatus(codes.Error, "invalid id format")
		http.Error(w, "Bad Request: invalid id format", http.StatusBadRequest)
		return
	}

	a, err := getAgency(ctx, h.pool, agencyID)
	if err == pgx.ErrNoRows {
		span.SetStatus(codes.Error, "agent not found or inactive")
		http.Error(w, "Not Found", http.StatusNotFound)
		return
	}
	if err != nil {
		span.SetStatus(codes.Error, "internal server error: "+err.Error())
		slog.Error("Error querying database", slog.Any("error", err))
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	defer func() { _ = r.Body.Close() }()
	var body bytes.Buffer
	_, _ = io.Copy(&body, r.Body)

	req, _ := http.NewRequestWithContext(ctx, r.Method, a.endpointURL, bytes.NewReader(body.Bytes()))
	req.Header = r.Header.Clone()

	span.SetAttributes(attribute.String("proxy.method", req.Method))
	span.SetAttributes(attribute.String("proxy.url", req.URL.String()))
	span.SetAttributes(attribute.String("proxy.body", body.String()))

	for _, apiHeader := range a.apiHeaders {
		req.Header.Set(apiHeader["name"], apiHeader["value"])
	}

	// collect keys first to avoid modifying map during iteration
	var toDelete []string
	for k := range req.Header {
		if strings.HasPrefix(k, "X-Forwarded") {
			toDelete = append(toDelete, k)
		}
	}
	for _, k := range toDelete {
		req.Header.Del(k)
	}
	for k, v := range req.Header {
		span.SetAttributes(attribute.String("proxy.request_header."+k, strings.Join(v, ",")))
	}

	startTime := now()
	resp, err := http.DefaultClient.Do(req)
	latency := now().Sub(startTime).Milliseconds()
	if err != nil {
		_ = h.addConnectionLog(ctx, agencyID, "error", latency, "error forwarding request: "+err.Error(), body.String(), "")
		span.SetStatus(codes.Error, "error forwarding request to backend: "+err.Error())
		slog.Error("Error forwarding request to backend", slog.Any("error", err))
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	span.SetAttributes(attribute.Int("proxy.response_status", resp.StatusCode))
	for k, v := range resp.Header {
		w.Header()[k] = v
		span.SetAttributes(attribute.String("proxy.response_header."+k, strings.Join(v, ",")))
	}
	w.WriteHeader(resp.StatusCode)

	var responseBody bytes.Buffer
	_, _ = io.Copy(&responseBody, resp.Body)
	_, _ = io.Copy(w, &responseBody)

	span.SetAttributes(attribute.String("proxy.response_body", responseBody.String()))

	if err := incrementTotalCalls(ctx, h.pool, agencyID); err != nil {
		span.SetStatus(codes.Error, "error updating total_calls: "+err.Error())
		slog.Error("Error updating total_calls", slog.Any("error", err))
	}

	var raw struct {
		Query string `json:"query"`
	}
	_ = json.Unmarshal(body.Bytes(), &raw)
	detail := fmt.Sprintf("Query: %s\n\nAnswer: %s", raw.Query, responseBody.String())

	status := "success"
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		status = "error"
	}
	_ = h.addConnectionLog(ctx, agencyID, status, latency, detail, body.String(), responseBody.String())

	span.SetStatus(codes.Ok, "request handled successfully")
}

func (h *handler) addConnectionLog(ctx context.Context, agencyID, status string, latency int64, detail, requestBody, responseBody string) error {
	ctx, span := h.tracer.Start(ctx, "Add Connection Log")
	defer span.End()

	if err := insertConnectionLog(ctx, h.pool, agencyID, status, latency, detail, requestBody, responseBody); err != nil {
		span.SetStatus(codes.Error, "error inserting connection log: "+err.Error())
		slog.Error("Error inserting connection log", slog.Any("error", err))
		return err
	}
	return nil
}
```

**Bugs fixed in this file vs original main.go:**
- `pathRegexp` and `uuidRegexp` are now package-level vars (compiled once).
- `X-Forwarded-*` header deletion collects keys first, then deletes — no map mutation during iteration.
- Response body copied directly: `io.Copy(w, &responseBody)` — no redundant second `NopCloser`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd agent-proxy && go test ./...
```

Expected:
```
--- PASS: TestServeHTTP_MissingID (0.00s)
--- PASS: TestServeHTTP_InvalidUUIDFormat (0.00s)
--- SKIP: TestGetAgency_NotFound (0.00s)
    store_test.go:14: DATABASE_URL not set
PASS
ok  	github.com/willywotz/thai-citizen-guide/agent-proxy	0.003s
```

- [ ] **Step 5: Tidy go.mod** (handler.go now directly imports `go.opentelemetry.io/otel/trace`)

```bash
cd agent-proxy && go mod tidy
```

Expected: `go.mod` promotes `go.opentelemetry.io/otel/trace` from indirect to direct.

- [ ] **Step 6: Commit**

```bash
rtk git add agent-proxy/handler.go agent-proxy/handler_test.go agent-proxy/go.mod agent-proxy/go.sum
rtk git commit -m "refactor(agent-proxy): extract handler struct into handler.go"
```

---

## Task 4: Rewrite main.go

**Files:**
- Modify: `agent-proxy/main.go`

- [ ] **Step 1: Replace main.go with startup-only wiring**

Replace the entire file with:

```go
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.40.0"
)

func init() {
	slog.SetLogLoggerLevel(slog.LevelDebug)
}

func main() {
	ctx := context.Background()

	slog.Info("Connecting to PostgreSQL database")
	cfg := mustPanic(pgxpool.ParseConfig(os.Getenv("DATABASE_URL")))
	cfg.AfterConnect = func(ctx context.Context, conn *pgx.Conn) error {
		_, err := conn.Exec(ctx, "SET TIMEZONE TO 'Asia/Bangkok'")
		return err
	}
	pool := mustPanic(pgxpool.NewWithConfig(ctx, cfg))
	defer pool.Close()

	tp, err := initTracer(ctx)
	if err != nil {
		slog.Error("Failed to initialize tracer", slog.Any("error", err))
		return
	}
	defer func() {
		if err := tp.Shutdown(ctx); err != nil {
			slog.Error("Error shutting down tracer provider", slog.Any("error", err))
		}
	}()

	http.Handle("/agent-proxy/", &handler{pool: pool, tracer: otel.Tracer("agent-proxy")})
	http.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("ok\n"))
	})

	slog.Info("Starting HTTP server on http://localhost:8080")
	_ = http.ListenAndServe(":8080", nil)
}

func mustPanic[T any](v T, err error) T {
	if err != nil {
		panic(err)
	}
	return v
}

func initTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint("jaeger:4317"),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String("agent-proxy"),
		),
	)
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	return tp, nil
}
```

Changes from original: removed `proxyHandler` closure and `addConnectionLog` closure (both moved to `handler.go`), wires `&handler{pool, tracer}` directly, renamed `InitTracer` → `initTracer` (unexported, only used within this package).

- [ ] **Step 2: Verify build**

```bash
cd agent-proxy && go build ./...
```

Expected: no output (clean build).

- [ ] **Step 3: Run all tests**

```bash
cd agent-proxy && go test ./...
```

Expected:
```
--- PASS: TestServeHTTP_MissingID (0.00s)
--- PASS: TestServeHTTP_InvalidUUIDFormat (0.00s)
--- SKIP: TestGetAgency_NotFound (0.00s)
    store_test.go:14: DATABASE_URL not set
PASS
ok  	github.com/willywotz/thai-citizen-guide/agent-proxy	0.003s
```

- [ ] **Step 4: Lint**

```bash
cd agent-proxy && golangci-lint run --allow-parallel-runners
```

Expected: no issues. If any, run `golangci-lint run --fix --allow-parallel-runners` to auto-fix, then re-run until clean.

- [ ] **Step 5: Commit**

```bash
rtk git add agent-proxy/main.go
rtk git commit -m "refactor(agent-proxy): slim main.go to startup wiring only"
```
