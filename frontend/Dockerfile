# ── Stage 1: Build (TanStack Start + Nitro node-server) ─────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --silent 2>/dev/null || npm install --silent

COPY . .

# Empty = relative /api paths (nginx reverse proxy handles routing in Docker)
ARG VITE_API_URL=""
ARG VITE_WS_URL=""
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

RUN npm run build

# ── Stage 2: Nitro Node server ───────────────────────────────────────────────
FROM node:20-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

COPY --from=builder /app/.output ./.output

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -qO- http://127.0.0.1:3000/ 2>/dev/null || exit 1

CMD ["node", ".output/server/index.mjs"]
