import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiTarget = process.env.ARIA_API_PROXY_TARGET ?? "http://localhost:8765";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  // @ts-expect-error — vitest config, ignored by vite build
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
