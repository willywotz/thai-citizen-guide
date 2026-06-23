package main

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
)

func TestAgencyCache_HitWithinTTL(t *testing.T) {
	var calls int
	c := newAgencyCache(func(_ context.Context, _ string) (agency, error) {
		calls++
		return agency{endpointURL: "u"}, nil
	}, time.Minute)

	for range 3 {
		if _, err := c.get(context.Background(), "id"); err != nil {
			t.Fatalf("get: %v", err)
		}
	}
	if calls != 1 {
		t.Fatalf("loader calls: want 1, got %d", calls)
	}
}

func TestAgencyCache_ExpiryReloads(t *testing.T) {
	var calls int
	c := newAgencyCache(func(_ context.Context, _ string) (agency, error) {
		calls++
		return agency{}, nil
	}, 0) // zero TTL: every get is a miss

	_, _ = c.get(context.Background(), "id")
	_, _ = c.get(context.Background(), "id")
	if calls != 2 {
		t.Fatalf("loader calls: want 2, got %d", calls)
	}
}

func TestAgencyCache_Invalidate(t *testing.T) {
	var calls int
	c := newAgencyCache(func(_ context.Context, _ string) (agency, error) {
		calls++
		return agency{}, nil
	}, time.Minute)

	_, _ = c.get(context.Background(), "id")
	c.invalidate("id")
	_, _ = c.get(context.Background(), "id")
	if calls != 2 {
		t.Fatalf("loader calls: want 2, got %d", calls)
	}
}

func TestAgencyCache_DoesNotCacheNotFound(t *testing.T) {
	var calls int
	c := newAgencyCache(func(_ context.Context, _ string) (agency, error) {
		calls++
		return agency{}, pgx.ErrNoRows
	}, time.Minute)

	_, _ = c.get(context.Background(), "id")
	_, err := c.get(context.Background(), "id")
	if !errors.Is(err, pgx.ErrNoRows) {
		t.Fatalf("want ErrNoRows, got %v", err)
	}
	if calls != 2 {
		t.Fatalf("ErrNoRows must not be cached: want 2 calls, got %d", calls)
	}
}
