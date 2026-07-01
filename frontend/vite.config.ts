import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In production the dashboard is served under /fraud-detection/ (behind the host
// nginx on https://ai.arttechgroup.com:7777). We only apply that base to the
// build so the local dev server (`npm run dev`) stays at http://localhost:5174/.
// The router basename and JSON data loader both derive from import.meta.env.BASE_URL,
// so they follow this automatically in both dev and prod.
// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/fraud-detection/" : "/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    open: false,
  },
}));
