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
