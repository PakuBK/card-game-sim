import path from "path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite-plus";
import react from "@vitejs/plugin-react";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  staged: {
    "*": "vp check --fix",
  },
  lint: {
    options: { typeAware: true, typeCheck: true },
    ignorePatterns: [
      "dist/**",
      "src/routeTree.gen.ts",
      "src/api/generated/**",
      ".fallowrc.json",
      ".github/**",
    ],
  },
  fmt: {
    ignorePatterns: [
      "dist/**",
      "src/routeTree.gen.ts",
      "src/api/generated/**",
      ".fallowrc.json",
      ".github/**",
    ],
  },
});
