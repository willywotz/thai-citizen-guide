from node:24 as base
env PNPM_HOME="/pnpm" \
    PATH="$PNPM_HOME:$PATH"
run corepack enable && corepack prepare pnpm@latest --activate

workdir /app
copy package.json package-lock.json pnpm-lock.yaml pnpm-workspace.yaml ./
run --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

from base as development
copy . .
cmd ["pnpm", "run", "dev"]

from base as builder
copy . .
run pnpm run build

from nginx as production
run apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
copy --from=builder /app/dist /usr/share/nginx/html
copy nginx.conf /etc/nginx/conf.d/default.conf