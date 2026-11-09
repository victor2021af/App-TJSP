import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, o Vite (porta 5173) repassa /api para o backend (porta 8000).
// Em produção, o próprio backend serve o frontend compilado (frontend/dist) na mesma origem.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", sourcemap: false },
});
