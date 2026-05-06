package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
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
	dsn := os.Getenv("DATABASE_URL")

	slog.Info("Connecting to PostgreSQL database")
	pool := mustPanic(pgxpool.New(ctx, dsn))

	tp, err := InitTracer(ctx)
	if err != nil {
		slog.Error("Failed to initialize tracer", slog.Any("error", err))
		return
	}
	defer func() {
		if err := tp.Shutdown(ctx); err != nil {
			slog.Error("Error shutting down tracer provider", slog.Any("error", err))
		}
	}()

	tracer := otel.Tracer("agent-proxy")

	addConnectionLog := func(ctx context.Context, agencyID string, status string, latency int64, detail string, request_body string, response_body string) {
		ctx, span := tracer.Start(ctx, "Add Connection Log")
		defer span.End()

		q := "insert into connection_logs (id, action, connection_type, status, latency_ms, detail, created_at, agency_id, request_body, response_body) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
		_, err := pool.Exec(ctx, q, uuidV7(), "proxy", "API", status, latency, detail, now(), agencyID, request_body, response_body)
		if err != nil {
			span.SetStatus(codes.Error, "error inserting connection log: "+err.Error())
			slog.Error("Error inserting connection log", slog.Any("error", err))
		}
	}

	proxyHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), "Handle HTTP Request")
		defer span.End()

		agentID := regexp.MustCompile(`^/agent-proxy/([^/]+)`).FindStringSubmatch(r.URL.Path)
		if len(agentID) < 2 {
			span.SetStatus(codes.Error, "missing id")
			http.Error(w, "Bad Request: missing id", http.StatusBadRequest)
			return
		}

		if !regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`).MatchString(agentID[1]) {
			span.SetStatus(codes.Error, "invalid id format")
			http.Error(w, "Bad Request: invalid id format", http.StatusBadRequest)
			return
		}

		q := "select endpoint_url, api_headers from agencies where id = $1 and status = 'active'"
		var endpointURL string
		var apiHeaders []map[string]string
		err := pool.QueryRow(ctx, q, agentID[1]).Scan(&endpointURL, &apiHeaders)
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
		r.Body = io.NopCloser(bytes.NewBuffer(body.Bytes()))

		req, _ := http.NewRequestWithContext(ctx, r.Method, endpointURL, r.Body)
		req.Header = r.Header.Clone()

		span.SetAttributes(attribute.String("proxy.method", req.Method))
		span.SetAttributes(attribute.String("proxy.url", req.URL.String()))
		span.SetAttributes(attribute.String("proxy.body", body.String()))

		for _, header := range apiHeaders {
			req.Header.Set(header["name"], header["value"])
		}

		for k, v := range req.Header {
			if strings.HasPrefix(k, "X-Forwarded") {
				req.Header.Del(k)
			}
			span.SetAttributes(attribute.String("proxy.request_header."+k, strings.Join(v, ",")))
		}

		startTime := now()
		resp, err := http.DefaultClient.Do(req)
		latency := now().Sub(startTime).Milliseconds()
		if err != nil {
			addConnectionLog(ctx, agentID[1], "error", latency, "error forwarding request: "+err.Error(), body.String(), "")
			span.SetStatus(codes.Error, "error forwarding request to backend: "+err.Error())
			slog.Error("Error forwarding request to backend", slog.Any("error", err))
			http.Error(w, "Bad Gateway", http.StatusBadGateway)
			return
		}

		span.SetAttributes(attribute.Int("proxy.response_status", resp.StatusCode))

		defer func() { _ = resp.Body.Close() }()

		for k, v := range resp.Header {
			w.Header()[k] = v
			span.SetAttributes(attribute.String("proxy.response_header."+k, strings.Join(v, ",")))
		}

		w.WriteHeader(resp.StatusCode)

		var responseBody bytes.Buffer
		_, _ = io.Copy(&responseBody, resp.Body)
		resp.Body = io.NopCloser(bytes.NewBuffer(responseBody.Bytes()))
		_, _ = io.Copy(w, resp.Body)

		span.SetAttributes(attribute.String("proxy.response_body", responseBody.String()))

		q = "update agencies set total_calls = total_calls + 1 where id = $1"
		_, err = pool.Exec(ctx, q, agentID[1])
		if err != nil {
			span.SetStatus(codes.Error, "error updating total_calls: "+err.Error())
			slog.Error("Error updating total_calls", slog.Any("error", err))
		}

		var rawDetail struct {
			Query string `json:"query"`
		}
		_ = json.Unmarshal(body.Bytes(), &rawDetail)
		detail := fmt.Sprintf("Query: %s\n\nAnswer: %s", rawDetail.Query, responseBody.String())

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			addConnectionLog(ctx, agentID[1], "success", latency, detail, body.String(), responseBody.String())
		} else {
			addConnectionLog(ctx, agentID[1], "error", latency, detail, body.String(), responseBody.String())
		}

		span.SetStatus(codes.Ok, "request handled successfully")
	})

	http.Handle("/agent-proxy/", proxyHandler)

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
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

func InitTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint("otel-collector:4317"),
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
