// Candidate A — custom React: SVG timeline + dnd-kit.
// dnd-kit supplies the pointer lifecycle/sensor; we own all SVG geometry and
// the semantic snap (shared/geometry.js). This is the honest way to marry a
// DOM-transform-oriented drag lib with an SVG render model — a finding in
// itself (see VERDICT.md, criterion 6).
import React, { useEffect, useLayoutEffect, useRef, useState, useMemo } from "react";
import { createRoot } from "react-dom/client";
import {
  DndContext, useDraggable, PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import {
  loadFixture, LAYOUT, timeToX, xToTime, boardWidth, boardHeight, rowY, snapTime,
} from "/shared/geometry.js";

const fmt = (t) =>
  new Date(t).toLocaleString("en-US", {
    weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  });

function GrabBar({ model, phase }) {
  const { attributes, listeners, setNodeRef } = useDraggable({ id: "grab" });
  const g = model.grab;
  const x = timeToX(g.startMs, model);
  const w = Math.max(6, (g.durMs / 3600000) * LAYOUT.pxPerHour);
  const y = rowY(g.row) + 4;
  return (
    <g ref={setNodeRef} {...listeners} {...attributes} style={{ cursor: "grab" }}>
      <rect data-grab="1" x={x} y={y} width={w} height={LAYOUT.rowH - 8} rx="4"
            fill="var(--grab)" opacity={phase === "idle" ? 1 : 0.35} />
      <title>{g.work_orders?.join(",")} · grab me</title>
    </g>
  );
}

function App() {
  const [model, setModel] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | grabbing | dropped
  const [tentative, setTentative] = useState(null); // {time,row,snappedTo,deltaCost}
  const [latency, setLatency] = useState(null);
  const altRef = useRef(false);
  const t0Ref = useRef(0);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 3 } }));

  useEffect(() => { loadFixture().then(setModel); }, []);

  // Alt key toggles snap off.
  useEffect(() => {
    const d = (e) => { if (e.key === "Alt") altRef.current = true; };
    const u = (e) => { if (e.key === "Alt") altRef.current = false; };
    window.addEventListener("keydown", d); window.addEventListener("keyup", u);
    return () => { window.removeEventListener("keydown", d); window.removeEventListener("keyup", u); };
  }, []);

  // measure grab->shade latency: t0 at grab, paint time after shading renders.
  useLayoutEffect(() => {
    if (phase === "grabbing" && latency === null && t0Ref.current) {
      requestAnimationFrame(() => setLatency(+(performance.now() - t0Ref.current).toFixed(1)));
    }
  }, [phase, latency]);

  const ghostCostByRow = useMemo(() => {
    const m = {};
    if (model) model.ghosts.forEach((gh) => (m[gh.row] = gh));
    return m;
  }, [model]);

  function beginGrab() {
    t0Ref.current = performance.now();
    setLatency(null);
    setPhase("grabbing");
    const g = model.grab;
    setTentative({ time: g.startMs, row: g.row, snappedTo: "origin", deltaCost: 0 });
  }
  function moveTo(rawTime, targetRow) {
    if (!model) return;
    const snap = snapTime(rawTime, model, { alt: altRef.current });
    const gh = ghostCostByRow[targetRow];
    // cost delta shown when landing on a ghost row (Tier-1 pre-priced)
    const deltaCost = gh && Math.abs(gh.startMs - snap.time) < 45 * 60000 ? gh.cost_delta : null;
    setTentative({ time: snap.time, row: targetRow, snappedTo: snap.snappedTo, deltaCost });
  }
  function drop() { setPhase("dropped"); }
  function reset() { setPhase("idle"); setTentative(null); setLatency(null); }

  // dnd-kit lifecycle -> our geometry
  function onDragStart() { beginGrab(); }
  function onDragMove(e) {
    const g = model.grab;
    const rawTime = g.startMs + (e.delta.x / LAYOUT.pxPerHour) * 3600000;
    const rowShift = Math.round(e.delta.y / LAYOUT.rowH);
    moveTo(rawTime, Math.max(0, Math.min(model.rows.length - 1, g.row + rowShift)));
  }
  function onDragEnd() { drop(); }

  // harness hook (interim-A screenshot driver)
  useEffect(() => {
    if (!model) return;
    window.__spike = {
      ready: true, candidate: "A",
      grab: () => beginGrab(),
      moveToTime: (iso, opts = {}) => { altRef.current = !!opts.alt; moveTo(new Date(iso).getTime(), (opts.row ?? model.grab.row)); },
      moveToGhost: (i) => { const gh = model.ghosts[i]; moveTo(gh.startMs, gh.row); },
      setAlt: (v) => { altRef.current = !!v; },
      drop: () => drop(),
      reset: () => reset(),
      getState: () => ({ phase, tentative, latency }),
    };
  }, [model, phase, tentative, latency]);

  if (!model) return <div style={{ padding: 20 }}>loading fixture…</div>;
  const W = boardWidth(model), H = boardHeight(model);
  const g = model.grab;

  // day/6h gridlines
  const ticks = [];
  for (let t = model.win.start; t <= model.win.end; t += 6 * 3600000) {
    const isDay = new Date(t).getUTCHours() === 0;
    ticks.push({ t, x: timeToX(t, model), isDay });
  }

  return (
    <>
      <div className="topbar">
        <h1>Candidate A</h1><span className="tag">custom React · SVG + dnd-kit</span>
        <span className="status" id="status">
          phase: <b>{phase}</b>
          {latency !== null && <> · grab→shade <b>{latency}ms</b></>}
          {tentative && <> · snapped:<b>{tentative.snappedTo}</b> · {fmt(tentative.time)}
            {tentative.deltaCost != null && <> · <b>{tentative.deltaCost >= 0 ? "+" : "-"}${Math.abs(tentative.deltaCost)}</b></>}</>}
        </span>
        <button className="ghost" onClick={reset}>reset</button>
      </div>
      <div className="legend">
        <span><span className="sw" style={{ background: "var(--green)" }} />green: fits</span>
        <span><span className="sw" style={{ background: "var(--amber)" }} />amber: fits, displaces</span>
        <span><span className="sw" style={{ background: "#4a4f60" }} />dim: illegal</span>
        <span><span className="sw" style={{ background: "var(--ghost)" }} />ghost: pool placement (priced)</span>
        <span className="hint">drag the purple bar · hold <kbd>Alt</kbd> to disable snap</span>
      </div>
      <div className="board-scroll">
        <DndContext sensors={sensors} onDragStart={onDragStart} onDragMove={onDragMove} onDragEnd={onDragEnd}>
          <svg width={W} height={H} style={{ display: "block", background: "var(--bg)" }}>
            {/* row backgrounds + legality tint when grabbing */}
            {model.rows.map((r) => {
              const y = rowY(r.index);
              const tint = phase !== "idle"
                ? (r.legality === "green" ? "var(--green-fill)"
                  : r.legality === "amber" ? "var(--amber-fill)" : "var(--dim-fill)")
                : "transparent";
              return (
                <g key={r.resource_id}>
                  <rect x={LAYOUT.gutter} y={y} width={W - LAYOUT.gutter} height={LAYOUT.rowH}
                        fill={tint} stroke="var(--grid)" strokeWidth="0.5" />
                  {/* calendar working windows (gaps read as closures) */}
                  {r.windows.map((w, i) => (
                    <rect key={i} x={timeToX(w.start, model)} y={y}
                          width={Math.max(1, ((w.end - w.start) / 3600000) * LAYOUT.pxPerHour)}
                          height={LAYOUT.rowH} fill="rgba(255,255,255,0.028)" />
                  ))}
                  <text x={10} y={y + LAYOUT.rowH / 2 + 4} fill="var(--muted)" fontSize="11">{r.name}</text>
                  {phase !== "idle" && (
                    <circle cx={LAYOUT.gutter - 12} cy={y + LAYOUT.rowH / 2}
                            r="4" fill={r.legality === "green" ? "var(--green)" : r.legality === "amber" ? "var(--amber)" : "#4a4f60"} />
                  )}
                </g>
              );
            })}

            {/* time axis */}
            {ticks.map((tk, i) => (
              <g key={i}>
                <line x1={tk.x} y1={LAYOUT.header - 6} x2={tk.x} y2={H}
                      stroke="var(--grid)" strokeWidth={tk.isDay ? 1 : 0.5} />
                <text x={tk.x + 3} y={16} fill={tk.isDay ? "var(--ink)" : "var(--muted)"} fontSize="10">
                  {new Date(tk.t).toLocaleString("en-US", { weekday: tk.isDay ? "short" : undefined, hour: "2-digit", hour12: false, timeZone: "UTC" })}
                </text>
              </g>
            ))}

            {/* all real bars */}
            {model.bars.map((b) => b.isGrab ? null : (
              <rect key={b.id} x={timeToX(b.start, model)} y={rowY(b.row) + 5}
                    width={Math.max(2, ((b.end - b.start) / 3600000) * LAYOUT.pxPerHour)}
                    height={LAYOUT.rowH - 10} rx="3" fill="var(--bar)" opacity="0.85" />
            ))}

            {/* ghost overlays (Tier-1), shown when grabbing */}
            {phase !== "idle" && model.ghosts.map((gh, i) => {
              const gx = timeToX(gh.startMs, model);
              const gw = Math.max(6, (g.durMs / 3600000) * LAYOUT.pxPerHour);
              const gy = rowY(gh.row) + 4;
              return (
                <g key={i}>
                  <rect x={gx} y={gy} width={gw} height={LAYOUT.rowH - 8} rx="4"
                        fill="none" stroke="var(--ghost)" strokeWidth="1.6" strokeDasharray="4 3" />
                  <rect x={gx} y={gy} width={gw} height={LAYOUT.rowH - 8} rx="4" fill="var(--ghost)" opacity="0.12" />
                  <text x={gx + gw + 6} y={gy + LAYOUT.rowH / 2} fill="var(--ghost)" fontSize="11" fontWeight="700">
                    {gh.cost_label}
                  </text>
                </g>
              );
            })}

            {/* snap-target ticks along the header, shown when grabbing */}
            {phase !== "idle" && model.targets.map((tg, i) => (
              <line key={i} x1={timeToX(tg.time, model)} y1={LAYOUT.header - 4}
                    x2={timeToX(tg.time, model)} y2={LAYOUT.header}
                    stroke={tg.kind === "predecessor_finish" ? "var(--green)" : tg.kind === "ghost" ? "var(--ghost)" : "var(--muted)"}
                    strokeWidth="2" />
            ))}

            {/* the draggable grab bar */}
            <GrabBar model={model} phase={phase} />

            {/* tentative (hatched) bar following the snapped position */}
            {tentative && (
              <>
                <defs>
                  <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <rect width="6" height="6" fill="var(--grab)" opacity="0.25" />
                    <line x1="0" y1="0" x2="0" y2="6" stroke="var(--grab)" strokeWidth="2" />
                  </pattern>
                </defs>
                <line x1={timeToX(tentative.time, model)} y1={LAYOUT.header}
                      x2={timeToX(tentative.time, model)} y2={H}
                      stroke="var(--grab)" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
                <rect x={timeToX(tentative.time, model)} y={rowY(tentative.row) + 4}
                      width={Math.max(6, (g.durMs / 3600000) * LAYOUT.pxPerHour)} height={LAYOUT.rowH - 8}
                      rx="4" fill="url(#hatch)" stroke="var(--grab)" strokeWidth="1.5"
                      strokeDasharray={phase === "dropped" ? "0" : "4 2"} />
                {phase === "dropped" && (
                  <text x={timeToX(tentative.time, model) + 4} y={rowY(tentative.row) - 2}
                        fill="var(--grab)" fontSize="11" fontWeight="700">
                    tentative · {tentative.snappedTo}{tentative.deltaCost != null ? ` · ${tentative.deltaCost >= 0 ? "+" : "-"}$${Math.abs(tentative.deltaCost)}` : ""}
                  </text>
                )}
              </>
            )}
          </svg>
        </DndContext>
      </div>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
