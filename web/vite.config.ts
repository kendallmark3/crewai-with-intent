import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Must match DEFAULT_PORT / CREW_PORT in src/server.py, so the proxy always reaches this repo's server.
const DEFAULT_PORT = 8787;

function crewPort(raw: string | undefined): number {
  if (raw === undefined || raw.trim() === "") return DEFAULT_PORT;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`CREW_PORT must be a whole number between 1 and 65535, got "${raw}".`);
  }
  return port;
}

// In dev, Vite serves the UI and forwards /api to the Python server (python -m src.server).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": `http://127.0.0.1:${crewPort(process.env.CREW_PORT)}` },
  },
});
