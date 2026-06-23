package main

import (
	"context"
	"sync"
	"time"
)

type cacheEntry struct {
	value     agency
	expiresAt time.Time
}

type agencyLoader func(ctx context.Context, id string) (agency, error)

type agencyCache struct {
	load func(ctx context.Context, id string) (agency, error)
	ttl  time.Duration

	mu      sync.RWMutex
	entries map[string]cacheEntry
}

func newAgencyCache(load agencyLoader, ttl time.Duration) *agencyCache {
	return &agencyCache{
		load:    load,
		ttl:     ttl,
		entries: make(map[string]cacheEntry),
	}
}

func (c *agencyCache) get(ctx context.Context, id string) (agency, error) {
	c.mu.RLock()
	e, ok := c.entries[id]
	c.mu.RUnlock()
	if ok && time.Now().Before(e.expiresAt) {
		return e.value, nil
	}

	a, err := c.load(ctx, id)
	if err != nil {
		return agency{}, err // never cache errors (incl. pgx.ErrNoRows)
	}

	c.mu.Lock()
	c.entries[id] = cacheEntry{value: a, expiresAt: time.Now().Add(c.ttl)}
	c.mu.Unlock()
	return a, nil
}

func (c *agencyCache) invalidate(id string) {
	c.mu.Lock()
	delete(c.entries, id)
	c.mu.Unlock()
}
