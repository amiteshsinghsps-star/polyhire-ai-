FROM node:22-alpine

WORKDIR /app

# pnpm setup
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

# Copy workspace manifests first for cache
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/gateway/package.json ./apps/gateway/
COPY packages/shared-types/package.json ./packages/shared-types/

RUN pnpm install --frozen-lockfile || pnpm install

COPY packages/shared-types ./packages/shared-types
COPY apps/gateway ./apps/gateway

RUN pnpm --filter @polyhire/shared-types build && \
    pnpm --filter @polyhire/gateway build

EXPOSE 4000

CMD ["node", "apps/gateway/dist/index.js"]
