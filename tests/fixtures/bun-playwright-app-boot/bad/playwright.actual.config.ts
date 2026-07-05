import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/actual",
  use: {
    baseURL: "http://127.0.0.1:4173",
  },
  webServer: {
    command: "bun run src/server.ts",
    reuseExistingServer: false,
    timeout: 10_000,
    url: "http://127.0.0.1:4173",
  },
});
