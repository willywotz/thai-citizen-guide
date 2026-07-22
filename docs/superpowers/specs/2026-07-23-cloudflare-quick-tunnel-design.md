# Cloudflare Quick Tunnel for dev — design

Date: 2026-07-23
Branch: `feat/cloudflare-quick-tunnel` (off `dev`)

## Goal

Give the local dev stack a temporary public `https://` URL so the running site can be shared
with teammates and testers, without a Cloudflare account, DNS record, inbound port, or any
change to the production TLS path.

Purpose is **demo sharing only**. Webhook delivery, OAuth redirect URIs, and stable hostnames
are explicit non-goals — Quick Tunnels mint a new random hostname on every restart, which rules
those out anyway.

## Constraints

| Constraint | Consequence |
|---|---|
| Quick Tunnel hostname is random per restart | No config may hardcode a hostname |
| Cloudflare gives Quick Tunnels no SLA | Tunnel drops are expected; recovery must be automatic |
| Vite 5.4.21 carries the backported host check | `server.allowedHosts` is mandatory, not optional |
| Production TLS path (nginx + certbot) must not regress | All changes live in the dev override |

## Architecture

```
browser ──https──> Cloudflare edge ──QUIC (outbound only)──> cloudflared
                                                                 │
                                                          nginx:8080
                                                                 │
                                    routes.conf ─> frontend / backend / agent-proxy / jaeger
```

`cloudflared` joins `chatbot-network` and dials `nginx:8080` over the internal network, so
nothing new is published on the host. The connection to Cloudflare is outbound-only. TLS
terminates at the Cloudflare edge; nginx keeps serving plain HTTP on 8080 exactly as today.

`nginx/`, `docker-compose.yaml`, and the certbot/Let's Encrypt path are untouched. Every change
is additive and dev-only.

### Image-tag policy

Both new services track **`latest`**, which departs from the pinning convention in
`docker-compose.yaml` (`jaegertracing/jaeger:2.18.0`, `certbot/certbot:v5.1.0`, `pgvector/pgvector:pg16`).
The split is along a real line rather than an exception per service:

| | Tag | Why |
|---|---|---|
| Services in `docker-compose.yaml` | pinned | Ship to production. Reproducible builds and controlled upgrades matter |
| Services in `docker-compose.override.yaml` | `latest` | Dev-only, never deployed. A broken dev tunnel is noticed instantly and fixed by a re-pull |

For `cloudflared` specifically this is the safer direction anyway: it is a client of a moving
remote service and Cloudflare deprecates old clients server-side, so a stale pin eventually
produces connection failures that read like a local bug.

The cost is that `docker compose up` does not re-pull on its own, so a dev machine can sit on a
months-old `latest` and drift from a teammate's. The fix when the tunnel misbehaves is
`docker compose pull cloudflared`; this goes in the troubleshooting note in `docs/quickstart.md`.

### Why the gateway and not individual services

Tunnelling `nginx:8080` means the shared URL exercises the same routing contract
(`nginx/routes.conf`) that production uses — SPA, `/api`, `/agent-proxy`, `/jaeger` all reachable
under one origin, same-origin from the SPA's point of view. Tunnelling `frontend:8080` directly
would leave the SPA's `/api` calls with nowhere to go.

## Components

### 1. `cloudflared` service — `docker-compose.override.yaml`

Always-on in dev: it starts with an ordinary `docker compose up`, with no profile or wrapper to
remember.

```yaml
cloudflared:
  image: cloudflare/cloudflared:latest
  restart: unless-stopped
  command: tunnel --no-autoupdate --url http://nginx:8080 --metrics 0.0.0.0:2000
  networks:
    - chatbot-network
  depends_on:
    - nginx
```

The image tracks `latest`, per the image-tag policy above.

`--no-autoupdate` still applies: Cloudflare recommends disabling self-update in containers, where
the filesystem is ephemeral and an in-place update just causes a surprise restart. Version churn
comes from re-pulling the image instead.

`--metrics 0.0.0.0:2000` exposes the local metrics server (container-internal only, not published
to the host) that serves the tunnel hostname; this is what makes URL discovery structured rather
than log-scraping.

`depends_on` uses plain start ordering because the `nginx` service defines no healthcheck.
cloudflared tolerates its origin being briefly unreachable.

### 2. `scripts/tunnel-url.sh` — the poll-and-parse logic

The only component with real behaviour, so it lives in a real file rather than inline YAML —
that is what makes it testable. POSIX `sh`, using BusyBox `wget` — the same idiom every
healthcheck in `docker-compose.yaml` already uses.

```sh
#!/usr/bin/env sh
# Print the current Quick Tunnel URL. Polls cloudflared's metrics server, which
# serves the randomly assigned hostname at /quicktunnel.
set -eu

base="${1:-http://cloudflared:2000}"
timeout="${TUNNEL_URL_TIMEOUT:-60}"

i=0
while [ "$i" -lt "$timeout" ]; do
  host=$(wget -qO- "$base/quicktunnel" 2>/dev/null \
    | sed -n 's/.*"hostname":"\([^"]*\)".*/\1/p')
  if [ -n "$host" ]; then
    printf '\n=== DEV TUNNEL: https://%s ===\n\n' "$host"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done

echo "tunnel-url: no hostname from $base after ${timeout}s" >&2
exit 1
```

Taking the metrics base URL as `$1` is what makes the unit test possible: the test points it at a
local stub instead of the real container. `TUNNEL_URL_TIMEOUT` keeps the test fast.

BusyBox `wget` exits non-zero on an unreachable host or HTTP error, but it sits inside a pipeline
whose exit status is `sed`'s, so `set -e` does not trip — failures fall through to an empty
`$host` and the loop simply polls again. That is the intended behaviour, and the test covers it.

`scripts/` does not exist yet in this repo; this creates it.

### 3. `tunnel-url` sidecar — `docker-compose.override.yaml`

One-shot service that runs the script above, prints the banner, and exits.

```yaml
tunnel-url:
  image: alpine:latest
  restart: "no"
  networks:
    - chatbot-network
  depends_on:
    - cloudflared
  volumes:
    - ./scripts/tunnel-url.sh:/tunnel-url.sh:ro
  entrypoint: ["sh", "/tunnel-url.sh"]
```

`alpine` is a plain utility container — a shell and BusyBox `wget`, nothing else. Reusing an image
the stack already pulls, such as `redis:7-alpine`, would save the pull but make a reader wonder
why Redis is printing a tunnel URL. The only surface this depends on is `sh` + `wget` + `sed`,
which BusyBox has carried unchanged for years, so tracking `latest` costs nothing.

Mounting rather than inlining keeps one implementation for both entrypoints. This makes the URL
appear automatically in `docker compose up` output, and recoverable after `docker compose up -d`
via `docker compose logs tunnel-url`.

**Re-printing on demand.** When the tunnel has restarted and minted a new hostname:

```sh
docker compose run --rm --no-deps tunnel-url
```

`--no-deps` avoids restarting `cloudflared`, which would change the very URL being asked for.
This command goes in `docs/quickstart.md`.

### 4. `frontend/vite.config.ts`

```ts
server: {
  host: "::",
  port: 8080,
  allowedHosts: [".trycloudflare.com"],
  hmr: { overlay: false },
}
```

Required, not optional: Vite 5.4.21 includes the backported host check, so without this every
tunnelled request returns `Blocked request. This host is not allowed.` The leading dot makes it a
domain-suffix match, so it survives the hostname changing on each restart.

This affects the dev server only — production builds do not read `server`. The existing
`hmr.overlay: false` is preserved.

### 5. Documentation

- `docs/quickstart.md` — add a tunnel row to the origins table (alongside the existing local-dev
  and deployed-gateway rows).
- A short "sharing a dev environment" section covering how to get the URL, that it changes on
  restart, and the exposure caveat below.

## Data flow

**HTTP.** Browser → Cloudflare edge (TLS terminated) → cloudflared → `nginx:8080` →
`nginx/routes.conf` → frontend / backend / agent-proxy / jaeger. Unchanged routing.

**HMR.** The browser opens `wss://<random>.trycloudflare.com/`. nginx's `location /` already sets
`Upgrade` and `Connection "upgrade"`, and Vite derives its HMR URL from `window.location`, so it
lands on port 443 over `wss` without any `server.hmr` configuration.

**Forwarded headers.** nginx sees plain HTTP from cloudflared, so `X-Forwarded-Proto` is `http`
even though the browser used HTTPS. Verified as harmless: neither `backend/` nor `agent-proxy/`
reads that header, and `CORS_ORIGINS` defaults to `["*"]` (`backend/app/config.py:47`). The SPA
is same-origin through the gateway regardless.

## Error handling

| Failure | Behaviour |
|---|---|
| cloudflared cannot reach nginx | `restart: unless-stopped` retries; cause visible in `docker compose logs cloudflared` |
| Metrics endpoint not ready when sidecar polls | Bounded polling (~60s), then exit non-zero with an actionable message — never hangs indefinitely |
| Tunnel drops and restarts | A **new** URL is minted; the old one dies. Re-run `docker compose run --rm --no-deps tunnel-url` and reshare |
| Request arrives with an unexpected Host | Covered by the `.trycloudflare.com` suffix match; other hosts are still blocked by Vite as intended |

## Security posture

The tunnel URL is **public and unauthenticated**. Anyone holding the link reaches the entire dev
gateway, including `/jaeger`, `/docs`, `/redoc`, and `/openapi.json`. Because the tunnel is
always-on in dev, every `docker compose up` publishes that surface for as long as the stack runs.

**Decision: document this, do not enforce it.** Adding auth or per-path blocking to the tunnel is
scope creep for a share-a-demo tool, and any path allowlist would immediately drift from
`routes.conf`. The mitigations relied on instead: the hostname is random and unguessable, it is
not indexed, and it dies with the container. The exposure is stated plainly in `docs/quickstart.md`
so the tradeoff is a choice rather than a surprise.

Anyone needing a hardened share should use a named Cloudflare Tunnel with Access policies — a
different feature, out of scope here.

## Testing

Compose wiring itself is declarative and not meaningfully unit-testable. The one component with
real logic is the poll-and-parse in the sidecar, and that is where TDD applies.

**Unit (test-first).** `scripts/tunnel-url.sh` takes its metrics base URL as `$1`, so the test
serves a stub `/quicktunnel` response from a local directory and points the script at it. Write
the test failing, confirm the failure, then implement the loop. Cases:

| Case | Expected |
|---|---|
| Valid `{"hostname":"abc.trycloudflare.com"}` | stdout contains `https://abc.trycloudflare.com`, exit 0 |
| Malformed / empty JSON body | keeps polling, then times out non-zero |
| Endpoint unreachable | keeps polling, then times out non-zero |
| Timeout reached | exit 1, message on **stderr** not stdout |

`TUNNEL_URL_TIMEOUT` is set low in tests so the timeout cases run in about a second.

**Integration (manual, recorded in the design doc).** With the stack up:

1. `docker compose up` prints the tunnel banner.
2. `GET /` on the tunnel URL returns 200 and serves the SPA — confirms Vite `allowedHosts`.
3. The backend health path returns 200 through the tunnel — confirms `/api` routing.
4. Editing a file under `frontend/src` triggers an HMR update in the tunnelled browser tab.
5. `docker compose logs tunnel-url` still shows the URL after `docker compose up -d`.
6. `docker compose run --rm --no-deps tunnel-url` re-prints the same URL without disturbing the
   running tunnel.

## Out of scope

- Named/persistent Cloudflare Tunnels, DNS records, and Cloudflare Access policies
- Any use of the tunnel in CI or production
- Webhook or OAuth redirect-URI workflows (incompatible with a per-restart random hostname)
- Authentication or path restriction on the tunnelled surface (see Security posture)
