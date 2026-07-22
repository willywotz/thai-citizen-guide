# HTTPS / Let's Encrypt (HTTP-01)

The gateway serves TLS for one public hostname, with certificates issued and renewed
by a `certbot` container using the **HTTP-01** challenge over a shared webroot — no
DNS access required. Production host: `chatbotportal.opdc.ai.in.th`.

## How it fits together

| Piece | Role |
|---|---|
| `default.conf` | HTTP server (`:8080`). Serves `/.well-known/acme-challenge/` from the webroot; everything else redirects to HTTPS once a cert exists. |
| `tls.conf.template` | TLS server (`:8443`), rendered to `conf.d/tls.conf` with `CERT_DOMAIN` substituted. |
| `routes.conf` | The proxy routing contract, included by both servers so they never drift. |
| `nginx-tls.sh` | Runs from nginx's `/docker-entrypoint.d/`. Enables the TLS block only when the cert exists, then watches hourly and reloads on issuance/renewal. |
| `certbot` service | `certbot renew` every 12h against the `letsencrypt` volume. |
| volumes | `letsencrypt` (certs, `:ro` in nginx), `acme-challenge` (webroot, `:ro` in nginx). |

Without a certificate the stack is a plain HTTP gateway — nginx never fails to start on
a missing certificate file, and local dev needs no changes.

## Prerequisites

- `chatbotportal.opdc.ai.in.th` resolves to the host running compose.
- Port **80** is open to the public internet and published by the `nginx` service
  (`EXTERNAL_HTTP_PORT=80`). Let's Encrypt always validates HTTP-01 on port 80 and
  follows redirects; it cannot use any other port.
- Port **443** published (`EXTERNAL_HTTPS_PORT=443`).

## First issuance

On the prod host, with `CERT_DOMAIN` set in `.env`:

```bash
rtk docker compose up -d nginx                    # webroot must be reachable first
rtk curl http://chatbotportal.opdc.ai.in.th/.well-known/acme-challenge/probe   # expect 404, not a timeout

rtk docker compose run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot \
  -d chatbotportal.opdc.ai.in.th \
  --email "$CERT_EMAIL" --agree-tos --no-eff-email
```

Add `--dry-run` first to rehearse without burning rate limits (5 failed
validations per account/hostname/hour).

nginx picks the new cert up within the hour on its own; to cut that short:

```bash
rtk docker compose restart nginx
rtk curl -I https://chatbotportal.opdc.ai.in.th/
```

## Renewal

The `certbot` service renews unattended (certs renew at ~30 days remaining). nginx's
watcher notices the changed `fullchain.pem` and issues `nginx -s reload` — no restart,
no deploy needed. Check it:

```bash
rtk docker compose run --rm --entrypoint certbot certbot renew --dry-run
rtk docker compose logs nginx | grep '\[tls\]'
```

## Turning TLS off

Unset `CERT_DOMAIN` and restart nginx. The TLS server block and the HTTPS redirect
disappear; the certificate stays in the volume.
