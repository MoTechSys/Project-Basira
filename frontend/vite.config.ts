/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = "http://127.0.0.1:8000";
const BACKEND_PROXY = { "/v1": BACKEND, "/health": BACKEND, "/docs": BACKEND, "/openapi.json": BACKEND };

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: true, // dev server only: accept remote preview hostnames; production is a static build
    proxy: BACKEND_PROXY,
  },
  // `vite preview` serves the production bundle with the same proxy → Lighthouse measures real output
  preview: { host: true, port: 4173, allowedHosts: true, proxy: BACKEND_PROXY },
  build: { sourcemap: false, target: "es2022" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
