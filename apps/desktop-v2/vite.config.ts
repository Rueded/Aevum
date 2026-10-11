import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1422,
    strictPort: true,
    host: host || "0.0.0.0",
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1423,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
    proxy: {
      "/character": "http://127.0.0.1:8000",
      "/conversations": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/memory": "http://127.0.0.1:8000",
      "/relationship": "http://127.0.0.1:8000",
      "/desktop": "http://127.0.0.1:8000",
    },
  },
});
