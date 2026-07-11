// Vite config for the cockpit (docs/07 Phase 3 interim-A).
//
// Substrate decision (docs/04 2026-07-11 amendment): vis-timeline was SELECTED
// by the 3.0/3.0b bake-off; the cockpit productionizes it. Bundler is Vite 5
// (same as the throwaway spike, so the substrate's behaviour carries over
// unchanged) and the app is framework-free vanilla ES modules — the read-only
// board needs no component runtime; feel-iteration lives in src/tokens.css.
//
// The dev server PROXIES the API so the browser sees the cockpit and the API
// as one origin (no CORS on the FastAPI surface, by design — it is single-
// tenant-by-construction, docs/08). Point it at a running API with
//   MRE_API=http://localhost:8000 npm run dev
// The built app (npm run build) fetches the same relative paths, so it can be
// served from behind the API (or the test fixture server) with no rebuild.
import { defineConfig } from "vite";

const API = process.env.MRE_API || "http://localhost:8000";
const proxy = Object.fromEntries(
  ["/schedules", "/submissions", "/runs", "/health"].map((p) => [
    p,
    { target: API, changeOrigin: true },
  ]),
);

export default defineConfig({
  server: { port: 5175, strictPort: true, proxy },
  preview: { port: 5176, strictPort: true, proxy },
  build: { outDir: "dist", emptyOutDir: true },
});
