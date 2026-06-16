// vite.config.ts
// Adds a dev proxy so the frontend (port 5173) can reach the backend (port 8000)
// without CORS issues during development.
//
// In production (Docker), nginx handles the proxy — no changes needed here.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  // Node server bundle for Docker production (`.output/server/index.mjs`)
  nitro: { preset: "node" },
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      proxy: {
        // REST API
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          secure: false,
        },
        // WebSocket
        "/ws": {
          target: "ws://localhost:8000",
          ws: true,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    preview: {
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          secure: false,
        },
        "/ws": {
          target: "ws://localhost:8000",
          ws: true,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  },
});
