// COLLAPSIBLE DOCKS (Session 4B.28 Item 2(a)) — screen room.
//
// The board is the product; the tray, the coarse look-ahead strip and the ask
// panel are all permanently docked around it. At demo density that leaves the
// bars a band in the middle. Each dock now collapses to a LABELLED EDGE with a
// live count/status badge, and the collapsed state persists per browser.
//
// THE BADGE IS THE POINT, NOT THE COLLAPSE. A dock that folded away to nothing
// would make 122 orders beyond the horizon invisible — and "no schedulable
// demand can be silently invisible" is the Glass Box cardinal danger the tray
// exists to answer (4B.3a CU2(d)). So a collapsed dock still STATES ITS COUNT,
// in the edge, always. Collapsed means "not expanded", never "not there".
//
// DEFAULTS ARE A DECISION: tray and coarse start COLLAPSED (a stranger does not
// need 122 rows in their first ten seconds), the ask panel starts OPEN — it is
// the differentiator, and a stranger has to see that it exists at all.

const STORE_KEY = "mre-docks";

function readState() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}") || {}; }
  catch { return {}; }
}
function writeState(s) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(s)); }
  catch { /* private mode — the choice lives for this page only */ }
}

/**
 * Make `el` collapsible.
 *
 *   key            persistence key ("tray" | "coarse" | "ask")
 *   label          the word on the collapsed edge ("BEYOND THE HORIZON")
 *   badge()        → string | null: the live count/status, stated in BOTH
 *                   states. Called on every repaint, so a dock whose contents
 *                   changed cannot show a stale number.
 *   defaultOpen    what a browser with no stored choice does
 *   axis           "y" (default) for a dock that folds DOWNWARD to a bottom
 *                   edge, "x" for one that folds SIDEWAYS to a side edge. It
 *                   picks the chevron, and the chevron is the only thing on a
 *                   collapsed edge that says which way the dock went.
 *   onChange(open) optional — hosts that must relayout (the board sizes itself
 *                   to the space its docks leave)
 */

// Session 4B.34 Item 4 — THE CHEVRON POINTS ALONG THE AXIS IT ACTUALLY MOVES.
//
// Every dock drew the vertical disclosure pair (▾ open / ▸ collapsed), which is
// right for the tray and the coarse band and wrong for the ask column: ask
// collapses SIDEWAYS, so "▾" promised a fold the planner never got. The glyph
// now names the direction the gesture takes the dock — and `data-dir` carries it
// semantically, so a guard asserts the DIRECTION rather than a character.
const CHEV = {
  y: { open: { glyph: "▾", dir: "down" }, shut: { glyph: "▸", dir: "right" } },
  x: { open: { glyph: "▸", dir: "right" }, shut: { glyph: "◂", dir: "left" } },
};

export function makeCollapsible(el, { key, label, badge, defaultOpen = true,
                                      axis = "y", onChange } = {}) {
  if (!el) return null;
  const stored = readState();
  let open = key in stored ? !!stored[key] : !!defaultOpen;

  el.classList.add("dock");
  // The axis is on the ELEMENT, so the CSS that sizes a collapsed dock can be
  // written once for every dock rather than per dock (Item 1) — and so a dock
  // that folds sideways is never given a height collapse, which clips its own
  // edge out of reach (see cockpit.css).
  el.dataset.collapseAxis = axis;
  const edge = document.createElement("button");
  edge.type = "button";
  edge.className = "dock-edge";
  edge.dataset.dock = key;
  el.prepend(edge);

  function paint() {
    const b = badge ? badge() : null;
    edge.replaceChildren();
    const chev = document.createElement("span");
    chev.className = "de-chev";
    const c = (CHEV[axis] || CHEV.y)[open ? "open" : "shut"];
    chev.textContent = c.glyph;
    chev.dataset.dir = c.dir;
    const name = document.createElement("span");
    name.className = "de-label";
    name.textContent = label;
    edge.append(chev, name);
    if (b != null && b !== "") {
      const badgeEl = document.createElement("span");
      badgeEl.className = "de-badge";
      badgeEl.textContent = String(b);
      edge.appendChild(badgeEl);
    }
    edge.setAttribute("aria-expanded", open ? "true" : "false");
    edge.title = open ? `collapse ${label.toLowerCase()}`
                      : `expand ${label.toLowerCase()}`;
    el.classList.toggle("collapsed", !open);
  }

  function set(next) {
    open = !!next;
    const s = readState();
    s[key] = open;
    writeState(s);
    paint();
    if (onChange) onChange(open);
  }

  edge.addEventListener("click", () => set(!open));
  paint();
  if (onChange) onChange(open);

  return {
    el, edge,
    isOpen: () => open,
    set,
    toggle: () => set(!open),
    refresh: paint,
    probe: () => ({
      key, open, axis,
      label: edge.querySelector(".de-label").textContent,
      badge: (edge.querySelector(".de-badge") || {}).textContent || null,
      chevron: edge.querySelector(".de-chev").dataset.dir,
    }),
  };
}
