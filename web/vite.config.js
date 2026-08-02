import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server for the Mira web shell. The Python brain will run as a separate API
// (see docs/14-ui-strategy.md) — UI and backend stay independent in the monorepo.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    headers: {
      "Cache-Control": "no-store, max-age=0",
    },
    // host:true binds 0.0.0.0 so GitHub Codespaces can forward the port; allow the
    // forwarded *.app.github.dev origin (Vite blocks unknown hosts by default).
    host: true,
    open: !process.env.CODESPACES,
    allowedHosts: [".app.github.dev"],
    // Proxy the voice bridge so the browser connects SAME-ORIGIN (wss://<5173 host>/mira-ws).
    // In Codespaces a separate forwarded port lives on a different *.app.github.dev
    // subdomain whose tunnel relay rejects cross-origin WS upgrades (HTTP 426 + auth
    // cookie). Same-origin proxying sidesteps that entirely; works locally too.
    proxy: {
      "/mira-ws": {
        target: process.env.VITE_MIRA_WS_TARGET || "ws://localhost:8765",
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mira-ws/, ""),
      },
      // LiveAvatar session token is minted server-side (key never hits the browser).
      "/avatar-token": {
        target: process.env.VITE_MIRA_WS_TARGET?.replace(/^ws/, "http") || "http://localhost:8765",
        changeOrigin: true,
      },
      // REST endpoints (category browse, etc.) — forward to the Python backend.
      // Without this, /api/* hits Vite's SPA fallback and returns index.html,
      // so filter-chip fetches silently fail (resp.json() throws on HTML).
      "/api": {
        target: process.env.VITE_MIRA_WS_TARGET?.replace(/^ws/, "http") || "http://localhost:8765",
        changeOrigin: true,
      },
    },
  },
});
