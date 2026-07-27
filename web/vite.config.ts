import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { yuqueAssets } from "yuque-editor-core/vite-assets";

export default defineConfig({
  plugins: [react(), yuqueAssets()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // API runs on 8790 per .env (GOTIT_PORT); override via web/.env VITE_API_BASE_URL if needed.
      "/v1": "http://127.0.0.1:8790",
      "/health": "http://127.0.0.1:8790",
    },
  },
});
