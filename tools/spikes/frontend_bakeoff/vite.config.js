import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// Multi-page: one dev/preview server hosts both bake-off candidates.
export default defineConfig({
  root: ".",
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        candidate_a: resolve(__dirname, "candidate_a.html"),
        candidate_b: resolve(__dirname, "candidate_b.html"),
      },
    },
  },
});
