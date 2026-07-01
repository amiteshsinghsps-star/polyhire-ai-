FROM node:22-alpine

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/frontend/package.json ./apps/frontend/
COPY packages/shared-types/package.json ./packages/shared-types/
RUN pnpm install --frozen-lockfile || pnpm install

COPY packages/shared-types ./packages/shared-types
COPY apps/frontend ./apps/frontend
RUN pnpm --filter @polyhire/shared-types build

EXPOSE 5173
CMD ["pnpm", "--filter", "@polyhire/frontend", "dev", "--", "--host", "0.0.0.0"]
