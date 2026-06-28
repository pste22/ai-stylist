import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server for the Mira web shell. The Python brain will run as a separate API
// (see docs/14-ui-strategy.md) — UI and backend stay independent in the monorepo.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // host:true binds 0.0.0.0 so GitHub Codespaces can forward the port; allow the
    // forwarded *.app.github.dev origin (Vite blocks unknown hosts by default).
    host: true,
    open: !process.env.CODESPACES,
    allowedHosts: [".app.github.dev"],
  },
});
