from golang:1.26-alpine as base
workdir /app
copy go.mod go.sum ./
run --mount=type=cache,target=/go/pkg/mod \
    go mod download

from base as development
copy . .
cmd ["go", "run", "."]

from base as builder
copy . .
run --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /app/agent-proxy .

from alpine as production
run apk --no-cache add ca-certificates tzdata
copy --from=builder /app/agent-proxy /usr/local/bin/agent-proxy
cmd ["agent-proxy"]