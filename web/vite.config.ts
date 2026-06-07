import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Dev: vite serves the UI, proxies /api (HTTP + WebSocket) to the FastAPI manager.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
