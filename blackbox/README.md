# Blackbox API tests

Positive role-access checks against a running instance: every role can reach the API
endpoints its allowed pages call. A request is a failure only if rejected with 401/403.

## Prerequisite

The target instance must already have an admin account. The first admin cannot be
created via the API. Default expected admin: `admin@example.com` / `admin1234`.

## Setup

    cp .env.test.example .env.test   # edit if your URL/admin differ
    pnpm install

## Run

    pnpm test          # one-shot
    pnpm test:watch    # watch mode

`global-setup.ts` runs once: seeds default agencies, creates one `bb-<role>` user per
role (idempotent), and grants `bb-agency-owner` ownership of the first agency so its
owner-scoped detail endpoints have a real resource to read. The matrix lives in
`src/access-matrix.ts` and is shared with the e2e suite.
