/// <reference types="vitest/config" />
import { defineConfig } from "vite";

// npm run dev serves the page here and hands /api to a reader started beside it with python -m comicreader
export default defineConfig({
  server: { proxy: { "/api": "http://localhost:8082" } },
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
  // npm run coverage. every source file is counted, tested or not, so one no test touches shows as nothing
  // rather than being left out of the total
  test: {
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts"],
      reporter: ["text", "html"],
    },
  },
});
