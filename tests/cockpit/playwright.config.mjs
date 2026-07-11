// Playwright config for the cockpit screenshot harness (docs/07 Phase 3, CU5).
// Promoted from the throwaway bake-off spike (tools/spikes/frontend_bakeoff/
// harness/run_3b.mjs) into production test infra. Builds the cockpit and serves
// it + the captured API fixtures via the hermetic fixture server; the spec
// drives scripted states, captures screenshots, and asserts machine-checked
// numbers (incl. the standing C1 label-vs-bar drift regression). CI: headless.
import { defineConfig } from "@playwright/test";

const PORT = 5199;

export default defineConfig({
  testDir: ".",
  testMatch: /cockpit\.spec\.mjs/,
  outputDir: "./shots/_pw",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    viewport: { width: 1540, height: 900 },
    deviceScaleFactor: 2,
  },
  webServer: {
    // build the cockpit, then serve it + the fixtures. Cross-platform && (cmd
    // on Windows, sh on POSIX). Requires the fixtures to exist
    // (python tools/build_cockpit_fixture.py) — committed, so CI needs no solver.
    command: "npm --prefix ../../src/cockpit run build && node fixture-server.mjs",
    cwd: ".",
    port: PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
  },
});
