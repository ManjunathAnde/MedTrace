import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/investigate": {
        target: "https://med-intel-backend-803800925462.us-central1.run.app",
        changeOrigin: true,
      },
    },
  },
});
