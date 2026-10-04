import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: process.env["E2E_BASE"] ?? "http://127.0.0.1:5173", locale: "ar-SA" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  reporter: [["list"]],
});
