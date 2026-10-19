# syntax=docker/dockerfile:1.7
# Frontend image: Next.js 15 standalone server. Build context is ./frontend.
ARG NODE_VERSION=20
ARG PLAYWRIGHT_VERSION=1.64.0

# ---- 1. dependencies (cached on package*.json) ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

# ---- 2. production build -------------------------------------------------------------------------------------------------
FROM deps AS build
# NEXT_PUBLIC_* values are inlined into the browser bundle at build time, so they are build args.
# "/backend" = same-origin proxy: the Next server rewrites /backend/* to BACKEND_INTERNAL_URL (see next.config.mjs).
# Use an absolute URL (e.g. http://localhost:8000) to have the browser call the backend directly, or "demo" for demo-only.
ARG NEXT_PUBLIC_API_BASE=/backend
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE} BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
COPY . .
RUN --mount=type=cache,target=/app/.next/cache npm run build
# sharp (~37 MB) only serves next/image optimisation, which the app does not use; typescript is traced in from next.config only.
RUN rm -rf .next/standalone/node_modules/@img .next/standalone/node_modules/sharp .next/standalone/node_modules/typescript

# ---- 3. unit tests (compose --profile test): full node_modules + sources ---------------------------------------------------
FROM deps AS test
COPY . .
# Some specs read repo-level files through ../ (REPO_ROOT = /): provided by the `repo` named build context (compose additional_contexts).
COPY --from=repo tests/fixtures /tests/fixtures
COPY --from=repo configs /configs
COPY --from=repo src/vakeel_sahayak/schemas /src/vakeel_sahayak/schemas
ENV CI=1
CMD ["npm", "test"]

# ---- 4. Playwright e2e (compose --profile test): official image, the browsers match the pinned @playwright/test -----------
FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble AS e2e
WORKDIR /app
ENV CI=1 NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
COPY --from=repo tests/fixtures /tests/fixtures
COPY --from=repo configs /configs
COPY --from=repo src/vakeel_sahayak/schemas /src/vakeel_sahayak/schemas
CMD ["npx", "playwright", "test"]

# ---- 5. runtime (default target) ----------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -g 10001 -S web && adduser -u 10001 -S -G web web
COPY --from=build --chown=web:web /app/.next/standalone ./
COPY --from=build --chown=web:web /app/.next/static ./.next/static
COPY --from=build --chown=web:web /app/public ./public
USER web
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]
CMD ["node", "server.js"]
