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
// An accepted edit mints a new version id ``<base>-edit`` (CU1); it maps back to
// the base fixture directory so a rebind serves a coherent document (the harness
// asserts the state transitions, not a distinct moved-bar fixture).
const dirFor = (id) => DIRS[id] || DIRS[id.replace(/-edit(-\d+)?$/, "")] || FIX;
// On-demand pricing state (session 3.3 CU1): ops POSTed for pricing this
// session, keyed "<scheduleId>|<opId>". A GET /alternatives merges their ghosts.
const _PRIMED = new Set();
// Accepted edits this session, keyed by the new -edit version id → its decision.
// The edit-domain "summarize my changes" answer (CU2/CU5) is synthesized from
// this (the base run carries no edit evidence hermetically — the fixture server
// stands in for the real edit-domain, its established role).
const _EDITS = new Map();
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
      const sid = mSched[1];
      const doc = await load("schedule.json", dirFor(sid));
      // An accepted -edit version reflects its pin: relocate the pinned op's
      // assignment to the pin placement so a rebind actually REFLOWS it (R-M1
      // motion end-states need a real move to assert against).
      const dec = _EDITS.get(sid);
      const pin = dec && dec.pin;
      if (pin) {
        const a = (doc.assignments || []).find((x) => x.operation_ref === pin.pin_op_id);
        if (a && a.chunks && a.chunks.length) {
          const span = new Date(a.chunks[a.chunks.length - 1].end) - new Date(a.chunks[0].start);
          a.resource_id = pin.pin_resource_id;
          a.chunks[0].start = pin.pin_start_iso;
          a.chunks[a.chunks.length - 1].end = new Date(new Date(pin.pin_start_iso).getTime() + span).toISOString();
        }
      }
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(doc));
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
    // On-demand pricing (session 3.3 CU1): POST /alternatives/op/<op> primes the
    // op; a later GET /alternatives merges in its priced ghosts (replaying the
    // real append-to-pool behavior). Match this BEFORE the member-index route.
    const mOnDemand = p.match(/^\/schedules\/([^/]+)\/alternatives\/op\/([^/]+)$/);
    if (mOnDemand && req.method === "POST") {
      const [, sid, opId] = mOnDemand;
      const od = await loadMaybe("ondemand.json", dirFor(sid));
      if (od && od.op_id === opId) _PRIMED.add(`${sid}|${opId}`);
      res.writeHead(202, { "content-type": "application/json" });
      return res.end(envelope({ op_id: opId, status: "pricing" }));
    }
    // The full solved document behind one ghost (session 3.3 CU4): served as
    // member_<index>.json (404 when the fixture built none for this index).
    const mMember = p.match(/^\/schedules\/([^/]+)\/alternatives\/(\d+)$/);
    if (mMember && req.method === "GET") {
      const doc = await loadMaybe(`member_${mMember[2]}.json`, dirFor(mMember[1]));
      if (!doc) {
        res.writeHead(404, { "content-type": "application/json" });
        return res.end(errEnv(404, "no member document for this index"));
      }
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope(doc));
    }
    // Tier-1 ghosts (R-T1a) — the /alternatives payload. 404 when the fixture
    // built none (the read-only multi_route set): the drag surface stays green.
    const mAlt = p.match(/^\/schedules\/([^/]+)\/alternatives$/);
    if (mAlt && req.method === "GET") {
      const dir = dirFor(mAlt[1]);
      const alt = await loadMaybe("alternatives.json", dir);
      if (!alt) {
        res.writeHead(404, { "content-type": "application/json" });
        return res.end(errEnv(404, "no forced alternatives built"));
      }
      // merge any on-demand-priced members for ops primed this session (CU1)
      const od = await loadMaybe("ondemand.json", dir);
      if (od && _PRIMED.has(`${mAlt[1]}|${od.op_id}`)) {
        const have = new Set(alt.members.map((m) => m.member_index));
        for (const m of od.members || []) {
          if (!have.has(m.member_index)) alt.members.push(m);
        }
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
    // Accept a dropped bar's verdict (CU1): mint a new proposed version id and
    // echo a planner_edit decision. The delta rides from the canned sandbox so
    // the accepted card shows a real number.
    const mAccept = p.match(/^\/schedules\/([^/]+)\/accept$/);
    if (mAccept && req.method === "POST") {
      const sid = mAccept[1];
      const pin = JSON.parse((await body(req)) || "{}");
      const sb = await loadMaybe("sandbox.json", dirFor(sid));
      const canned = (sb && sb.by_op && sb.by_op[pin.pin_op_id]) || (sb && sb.default) || {};
      const newId = `${sid}-edit`;
      const decision = {
        record_id: "dec-" + Math.random().toString(36).slice(2, 10),
        authority: pin.authority || "dev-planner",
        delta_abs: canned.delta_abs ?? null, delta_pct: canned.delta_pct ?? null,
        moved_count: (canned.moves || []).length, pin,
      };
      _EDITS.set(newId, decision);
      res.writeHead(201, { "content-type": "application/json" });
      return res.end(envelope({
        schedule_id: newId, parent_schedule_id: sid, status: "proposed", decision,
      }));
    }
    // Publish an accepted version (CU1): proposed → published, superseding the
    // prior version.
    const mPublish = p.match(/^\/schedules\/([^/]+)\/publish$/);
    if (mPublish && req.method === "POST") {
      const sid = mPublish[1];
      const parent = sid.replace(/-edit(-\d+)?$/, "");
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(envelope({ schedule_id: sid, status: "published",
                                superseded: parent !== sid ? [parent] : [] }));
    }
    const mAsk = p.match(/^\/schedules\/([^/]+)\/ask$/);
    if (mAsk && req.method === "POST") {
      const sid = mAsk[1];
      const { question } = JSON.parse((await body(req)) || "{}");
      // CU5 closing beat: "summarize my changes" on an accepted -edit version →
      // synthesize the edit narrative from the remembered accept (the base run
      // has no edit evidence hermetically). The real decomposed answer is proven
      // by the Python end-to-end test against the live API.
      const dec = _EDITS.get(sid);
      if (dec && /summar|what.*chang|what i chang|my (change|edit)/i.test(question)) {
        const d = dec.delta_abs;
        const dstr = d == null ? "cost unknown"
          : `${d >= 0 ? "+" : "−"}$${Math.abs(d).toLocaleString()}`;
        const op8 = (dec.pin?.pin_op_id || "").slice(0, 8);
        const answer = `You accepted 1 edit on this version (${dstr} total):\n`
          + `  - pinned op ${op8} to its machine · ${dstr} · by ${dec.authority}\n\n`
          + `register: testimony`;
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(envelope({
          question, answer,
          bundle: { register: "testimony", subject_type: "edits",
                    cited_refs: { operations: [dec.pin?.pin_op_id].filter(Boolean),
                                  resources: [], demands: [] } },
        }));
      }
      const asks = await load("asks.json", dirFor(sid));
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
