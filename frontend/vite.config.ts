import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { fileURLToPath, URL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@assets": path.resolve(__dirname, "..", "attached_assets"),
    },
    dedupe: ["react", "react-dom"],
  },
  root: path.resolve(__dirname),
  build: {
    outDir: path.resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    allowedHosts: true,
    fs: {
      strict: true,
    },
    // Same-origin `/api/*` as in production nginx — point at local FastAPI (host port if using docker compose: 8000)
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_API_PROXY ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    host: "0.0.0.0",
    allowedHosts: true,
  },
});
