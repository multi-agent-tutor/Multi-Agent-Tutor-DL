import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5173 fixe : c'est l'origine autorisée par CORS dans api/main.py.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
});
