// Hermetic fixture server for the cockpit screenshot harness (docs/07 CU5).
// Serves the BUILT cockpit (src/cockpit/dist) AND a faithful stand-in for the
// live API — the exact envelope shapes the real FastAPI serves — from the
// captured fixtures (tools/build_cockpit_fixture.py). This lets CI render the
// real cockpit board and run the ask/highlight flow WITHOUT the Python solver
// in the browser test. The live acceptance moment uses the real API instead.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { extname, join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, "..", "..", "src", "cockpit", "dist");
const FIX = resolve(__dirname, "fixtures");
const PORT = parseInt(process.env.PORT || "5199", 10);

// Two hermetic fixture sets, keyed by schedule id → its directory:
//   * the SATURATED multi_route (read-only interim-A regressions)
//   * the DISTINCT-rate multi_route (the 3.2b gesture surface — real ghosts +
//     canned sandbox verdicts). See tools/build_cockpit_fixture.py.
const DIRS = {
  "sched-multi-route-fixture": FIX,
  "sched-multi-route-distinct": resolve(FIX, "distinct"),
};
const dirFor = (id) => DIRS[id] || FIX;
const load = async (name, dir = FIX) => JSON.parse(await readFile(join(dir, name), "utf-8"));
const loadMaybe = async (name, dir) => {
  const full = join(dir, name);
  return existsSync(full) ? JSON.parse(await readFile(full, "utf-8")) : null;
};
const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".map": "application/json",
};
const envelope = (data) => JSON.stringify({ api_version: "1", data });
const errEnv = (code, message) => JSON.stringify({ api_version: "1", error: { code, message } });

async function body(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return Buffer.concat(chunks).toString("utf-8");
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const p = url.pathname;

    // ---- API stand-in (same envelopes as mre.api.app) -------------------
    if (p === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope({ status: "ok", api_version: "1" }));
    }
    if (p === "/schedules" && req.method === "GET") {
      // both fixtures listed; the harness always selects via ?schedule=…
      const metas = [];
      for (const dir of new Set(Object.values(DIRS))) {
        const m = await loadMaybe("meta.json", dir);
        if (m) metas.push(m);
      }
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope({ schedules: metas }));
    }
    const mSched = p.match(/^\/schedules\/([^/]+)$/);
    if (mSched && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("schedule.json", dirFor(mSched[1]))));
    }
    const mMeta = p.match(/^\/schedules\/([^/]+)\/meta$/);
    if (mMeta && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("meta.json", dirFor(mMeta[1]))));
    }
    const mInteract = p.match(/^\/schedules\/([^/]+)\/interaction$/);
    if (mInteract && req.method === "GET") {
      // the Tier-0 payload, served separately (contract 1.3, R-T1d)
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("interaction.json", dirFor(mInteract[1]))));
    }
    // Tier-1 ghosts (R-T1a) — the /alternatives payload. 404 when the fixture
    // built none (the read-only multi_route set): the drag surface stays green.
    const mAlt = p.match(/^\/schedules\/([^/]+)\/alternatives$/);
    if (mAlt && req.method === "GET") {
      const alt = await loadMaybe("alternatives.json", dirFor(mAlt[1]));
      if (!alt) {
        res.writeHead(404, { "content-type": "application/json" });
        return res.end(errEnv(404, "no forced alternatives built"));
      }
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(alt));
    }
    // Tier-2 sandbox re-solve (R-DP1/R-T1c) — canned by pinned op. Returns the
    // outcome the fixture recorded for this op (verdict / flagged / no_verdict),
    // else the default verdict.
    const mSandbox = p.match(/^\/schedules\/([^/]+)\/sandbox$/);
    if (mSandbox && req.method === "POST") {
      const sb = await loadMaybe("sandbox.json", dirFor(mSandbox[1]));
      if (!sb) {
        res.writeHead(404, { "content-type": "application/json" });
        return res.end(errEnv(404, "no canned sandbox for this fixture"));
      }
      const { pin_op_id } = JSON.parse((await body(req)) || "{}");
      const result = (sb.by_op && sb.by_op[pin_op_id]) || sb.default;
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(result));
    }
    const mAsk = p.match(/^\/schedules\/([^/]+)\/ask$/);
    if (mAsk && req.method === "POST") {
      const { question } = JSON.parse((await body(req)) || "{}");
      const asks = await load("asks.json", dirFor(mAsk[1]));
      const hit = asks[question];
      if (!hit) {
        res.writeHead(404, { "content-type": "application/json" });
        return res.end(errEnv(404, `no canned answer for: ${question}`));
      }
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(hit));
    }

    // ---- static: the built cockpit --------------------------------------
    let file = p === "/" ? "/index.html" : p;
    let full = join(DIST, file);
    if (!existsSync(full)) full = join(DIST, "index.html"); // SPA fallback
    const data = await readFile(full);
    res.writeHead(200, { "content-type": MIME[extname(full)] || "application/octet-stream" });
    return res.end(data);
  } catch (e) {
    res.writeHead(500, { "content-type": "application/json" });
    res.end(errEnv(500, String(e.message || e)));
  }
});

server.listen(PORT, () => console.log(`cockpit fixture server on http://localhost:${PORT}`));
