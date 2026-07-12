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

const load = async (name) => JSON.parse(await readFile(join(FIX, name), "utf-8"));
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
      const meta = await load("meta.json");
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope({ schedules: [meta] }));
    }
    const mSched = p.match(/^\/schedules\/([^/]+)$/);
    if (mSched && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("schedule.json")));
    }
    const mMeta = p.match(/^\/schedules\/([^/]+)\/meta$/);
    if (mMeta && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("meta.json")));
    }
    const mInteract = p.match(/^\/schedules\/([^/]+)\/interaction$/);
    if (mInteract && req.method === "GET") {
      // the Tier-0 payload, served separately (contract 1.3, R-T1d)
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(await load("interaction.json")));
    }
    const mAsk = p.match(/^\/schedules\/([^/]+)\/ask$/);
    if (mAsk && req.method === "POST") {
      const { question } = JSON.parse((await body(req)) || "{}");
      const asks = await load("asks.json");
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
