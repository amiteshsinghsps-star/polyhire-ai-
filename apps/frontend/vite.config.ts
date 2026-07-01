import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// PolyHire frontend dev server. The gateway URL is configurable so the
// Dockerized build can point at the in-network gateway hostname.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  define: {
    "import.meta.env.VITE_GATEWAY_URL": JSON.stringify(
      process.env.VITE_GATEWAY_URL ?? "http://localhost:4000",
    ),
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
});
