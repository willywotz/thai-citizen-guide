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
