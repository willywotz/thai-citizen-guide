#!/usr/bin/env sh
# Print the current Cloudflare Quick Tunnel URL.
#
# Quick Tunnels mint a new random hostname on every restart, so the URL cannot
# be configured — it has to be read back from cloudflared at runtime. The
# metrics server serves it as JSON at /quicktunnel, which is stabler than
# scraping the startup banner out of the logs.
#
# The base URL is a parameter so the tests can point at a stub server.
set -eu

base="${1:-http://cloudflared:2000}"
# Number of poll attempts, NOT seconds: each attempt is bounded by wget's -T 5
# plus a 1s sleep, so wall time is roughly attempts * 6s, not attempts * 1s.
attempts="${TUNNEL_URL_TIMEOUT:-60}"

i=0
while [ "$i" -lt "$attempts" ]; do
  # wget exits non-zero when cloudflared is not up yet, but it sits in a
  # pipeline whose status is sed's, so `set -e` does not trip here: a failed
  # fetch falls through to an empty $host and we simply poll again.
  # -T 5 bounds a single request even if cloudflared accepts the TCP
  # connection but never responds (busybox wget's default -T is 900s).
  host=$(wget -T 5 -qO- "$base/quicktunnel" 2>/dev/null \
    | sed -n 's/.*"hostname":"\([^"]*\)".*/\1/p')
  if [ -n "$host" ]; then
    printf '\n=== DEV TUNNEL: https://%s ===\n\n' "$host"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done

echo "tunnel-url: no hostname from $base after $attempts attempts" >&2
exit 1
