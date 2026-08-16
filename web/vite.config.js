import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";

// Dev server for the Mira web shell. The Python brain will run as a separate API
// (see docs/14-ui-strategy.md) — UI and backend stay independent in the monorepo.
// basicSsl enables https://127.0.0.1:5173 for local OAuth / secure-context APIs.
export default defineConfig({
  plugins: [react(), basicSsl()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          // posthog is dynamically imported — don't force an empty named chunk
          if (id.includes("posthog")) return;
          if (id.includes("@rive-app")) return "rive";
          if (id.includes("@heygen")) return "heygen";
          if (id.includes("@supabase")) return "supabase";
          if (id.includes("react-dom") || id.includes("/react/")) return "react-vendor";
        },
      },
    },
  },
  server: {
    port: 5173,
    https: true,
    headers: {
      "Cache-Control": "no-store, max-age=0",
    },
    // host:true binds 0.0.0.0 so GitHub Codespaces can forward the port; allow the
    // forwarded *.app.github.dev origin (Vite blocks unknown hosts by default).
    host: true,
    strictPort: true,
    open: false,
    // true: allow Cursor port-forward, Codespaces, and public HTTPS tunnels.
    allowedHosts: true,
    // Behind a tunnel the page is served on 443, but Vite's HMR client derives the
    // socket port from the dev-server port and ends up dialling a port the tunnel
    // never exposes. VITE_HMR_CLIENT_PORT lets dev.sh point it at the public port.
    hmr: process.env.VITE_HMR_CLIENT_PORT
      ? {
          clientPort: Number(process.env.VITE_HMR_CLIENT_PORT),
          protocol: process.env.VITE_HMR_PROTOCOL || "wss",
        }
      : true,
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
