# UI e2e tests (Playwright)

Drives the real frontend as each role: visits every page the role is allowed to see and
asserts (a) it is not redirected away and (b) no background `/api` call returns 401/403.

## Prerequisite

A running instance with an existing admin (see ../blackbox/README.md). Browser +
host libraries:

    pnpm playwright install --with-deps chromium

(`--with-deps` installs the OS libraries Chromium needs; it requires sudo.)

## Setup

    cp .env.test.example .env.test   # edit if URL/admin differ
    pnpm install

## Run

    pnpm test

`global-setup.ts` reuses the blackbox provisioning helpers (same `bb-<role>` accounts,
access matrix, and agency-owner grant), logs in each role, and saves a `.auth/<role>.json`
storage state used by the specs.
