// The screens' build and development server. In development the page is served from localhost:5173 and every /api
// request is passed on to the backend on port 8000, so for the browser both come from one origin and the session
// cookie can stay SameSite=Strict.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
});
