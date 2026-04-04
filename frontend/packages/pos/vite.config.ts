import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/pos/",
  plugins: [react()],
  server: {
    port: 3003,
    proxy: {
      "/api": { target: "http://localhost:8000", ws: true },
    },
  },
});
