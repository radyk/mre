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
  testMatch: /\.spec\.mjs$/,
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
  // Theme is a first-class harness dimension (Session 4.1 CU3): every RENDERING
  // spec runs on BOTH data-themes (each boot appends &theme=<project theme>; the
  // C1 label-vs-bar drift regression is therefore asserted per theme). The
  // pure-JS Tier-0 legality tests have no rendering, so they run once, theme-
  // free. Screenshots are suffixed by theme (shots/ is gitignored).
  projects: [
    // `carriedstate` is R-MT1's client half (Session 4A teaching-graft (d.1)).
    // It asserts what a REQUEST carries across an in-place version rebind —
    // nothing about it is theme-sensitive, so it runs once like the other
    // state/logic specs rather than twice like the rendering ones.
    { name: "logic", testMatch: /(legality|rowstats|freshness|schedulepicker|attribution|three_way_card|lineage|carriedstate)\.spec\.mjs$/ },
    {
      name: "light", metadata: { theme: "light" },
      testMatch: /(cockpit|gesture|rehearsal|planner|rolling|rolling\.two_beat|beat_two|deeplink|coarse|boundary|guipolish|oneclock)\.spec\.mjs$/,
    },
    {
      name: "dark", metadata: { theme: "dark" },
      testMatch: /(cockpit|gesture|rehearsal|planner|rolling|rolling\.two_beat|beat_two|deeplink|coarse|boundary|guipolish)\.spec\.mjs$/,
    },
  ],
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
