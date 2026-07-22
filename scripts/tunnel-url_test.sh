#!/usr/bin/env sh
# Tests scripts/tunnel-url.sh against a stub HTTP server standing in for
# cloudflared's metrics endpoint. No test framework: this is the only shell
# script in the repo, so a bats dependency would cost more than it saves.
set -eu

dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
script="$dir/tunnel-url.sh"
failures=0

for cmd in python3 wget; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "tunnel-url_test: $cmd is required to run these tests" >&2
    exit 1
  }
done

free_port() {
  python3 -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()'
}

# Serves $1 as the body of /quicktunnel. Sets $stub_base for the caller.
start_stub() {
  stub_dir=$(mktemp -d)
  printf '%s' "$1" > "$stub_dir/quicktunnel"
  stub_port=$(free_port)
  python3 -m http.server "$stub_port" --bind 127.0.0.1 \
    --directory "$stub_dir" >/dev/null 2>&1 &
  stub_pid=$!
  stub_base="http://127.0.0.1:$stub_port"
  # Block until the listener accepts, otherwise the first poll races startup
  # and the "valid response" case flakes.
  i=0
  while [ "$i" -lt 50 ]; do
    wget -qO- "$stub_base/quicktunnel" >/dev/null 2>&1 && return 0
    i=$((i + 1))
    sleep 0.1
  done
  echo "tunnel-url_test: stub server never came up" >&2
  exit 1
}

stop_stub() {
  [ -n "${stub_pid:-}" ] && kill "$stub_pid" 2>/dev/null || true
  [ -n "${stub_dir:-}" ] && rm -rf "$stub_dir"
  stub_pid=
  stub_dir=
}
trap stop_stub EXIT INT TERM

check() {
  if [ "$2" = "$3" ]; then
    echo "ok - $1"
  else
    echo "FAIL - $1: expected [$3], got [$2]" >&2
    failures=$((failures + 1))
  fi
}

# --- valid response ---------------------------------------------------------
start_stub '{"hostname":"abc.trycloudflare.com"}'
out=$(TUNNEL_URL_TIMEOUT=5 sh "$script" "$stub_base") && status=0 || status=$?
stop_stub
check "valid response prints the URL" \
  "$(printf '%s' "$out" | grep -c 'https://abc\.trycloudflare\.com')" "1"
check "valid response exits 0" "$status" "0"

# --- malformed body ---------------------------------------------------------
start_stub 'not json at all'
out=$(TUNNEL_URL_TIMEOUT=2 sh "$script" "$stub_base" 2>/dev/null) \
  && status=0 || status=$?
stop_stub
check "malformed body exits 1" "$status" "1"
check "malformed body prints nothing on stdout" "$out" ""

# --- unreachable endpoint ---------------------------------------------------
dead_base="http://127.0.0.1:$(free_port)"
out=$(TUNNEL_URL_TIMEOUT=2 sh "$script" "$dead_base" 2>/dev/null) \
  && status=0 || status=$?
check "unreachable endpoint exits 1" "$status" "1"

# --- diagnostics go to stderr, keeping stdout pipe-safe ---------------------
err=$(TUNNEL_URL_TIMEOUT=2 sh "$script" "$dead_base" 2>&1 >/dev/null) || true
check "timeout message goes to stderr" \
  "$(printf '%s' "$err" | grep -c 'no hostname')" "1"

if [ "$failures" -ne 0 ]; then
  echo "$failures test(s) failed" >&2
  exit 1
fi
echo "all tunnel-url tests passed"
