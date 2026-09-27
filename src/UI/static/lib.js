// What every page of the panel shares: the server, the DOM helper, the
// chart theme, icons and the modal.

// ---------------- server ----------------

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "content-type": "application/json" }, ...options });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `${response.status} ${response.statusText}`);
  }

  return response.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });
const world = (id, tail) => `/api/worlds/${encodeURI(id)}/${tail}`;

// Only the parts of a filter that are set: an empty filter must leave the
// address alone, so an unfiltered chart takes the cheap path on the server.
function query(filter) {
  const parts = Object.entries(filter || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "" && value !== "all")
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`);

  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  worlds: () => request("/api/worlds"),
  facets: () => request("/api/facets"),
  metrics: () => request("/api/metrics"),
  config: () => request("/api/config"),

  details: (id) => request(world(id, "details")),
  // A chart can be about a part of the population: see reports.cohorts.
  rewards: (id, filter) => request(world(id, `rewards${query(filter)}`)),
  learning: (id, filter) => request(world(id, `learning${query(filter)}`)),
  family: (id) => request(world(id, "family")),
  agent: (id, agentId) => request(world(id, `agent/${encodeURIComponent(agentId)}`)),
  heatmap: (id) => request(world(id, "heatmap")),
  stream: (id) => new EventSource(world(id, "stream")),

  resume: (id, body) => post(world(id, "continue"), body),
  watch: (id, speed) => post(world(id, "watch"), { speed }),
  stopWorld: (id) => post(world(id, "stop"), {}),
  keep: (id) => post(world(id, "keep"), {}),
  rename: (id, label) => post(world(id, "rename"), { label }),
  archive: (id, note, remove) => post(world(id, "archive"), { note, delete: remove }),
  remove: (id) => request(`/api/worlds/${encodeURI(id)}`, { method: "DELETE" }),
  compare: (worlds, metric) => post("/api/compare", { worlds, metric }),

  runs: () => request("/api/runs"),
  launch: (body) => post("/api/runs", body),
  runWorld: (id) => request(`/api/runs/${id}/world`),
  stop: (id) => request(`/api/runs/${id}`, { method: "DELETE" }),
  console: (id) => request(`/api/runs/${id}/console`),
  clear: () => post("/api/runs/clear", {}),
};

// ---------------- routes ----------------
// Every page is a hash route, so the browser's own back and forward
// buttons walk through the panel the way they walk through any site.

export const route = {
  worlds: () => "#/",
  world: (id) => `#/world/${encodeURIComponent(id)}`,
  compare: (step = "") => `#/compare${step ? `/${step}` : ""}`,
  launch: () => "#/launch",
  live: (id) => `#/live/${encodeURIComponent(id)}`,
  liveRun: (runId) => `#/live-run/${encodeURIComponent(runId)}`,
};

export function go(hash) { location.hash = hash; }

// ---------------- DOM ----------------

export function h(tag, attributes = {}, children = []) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;

    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }

  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }

  return node;
}

// ---------------- icons ----------------
// Line icons drawn in the current text colour, 16px.

const PATHS = {
  open: '<path d="M2 8s2.2-4.5 6-4.5S14 8 14 8s-2.2 4.5-6 4.5S2 8 2 8Z"/><circle cx="8" cy="8" r="1.8"/>',
  watch: '<rect x="1.8" y="3.5" width="9" height="9" rx="1.6"/><path d="m10.8 6.6 3.4-2v6.8l-3.4-2"/>',
  resume: '<path d="M5 3.2v9.6L12.6 8Z"/>',
  replay: '<path d="M2.8 8a5.2 5.2 0 1 0 1.6-3.8"/><path d="M2.6 2.4v2.8h2.8"/>',
  archive: '<rect x="1.8" y="2.6" width="12.4" height="3.2" rx=".8"/><path d="M3 5.8v6.8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5.8M6.4 8.6h3.2"/>',
  delete: '<path d="M2.6 4.2h10.8M6.2 4.2V2.8h3.6v1.4M3.9 4.2l.7 9h6.8l.7-9"/>',
  stop: '<rect x="4" y="4" width="8" height="8" rx="1.2"/>',
  plus: '<path d="M8 3v10M3 8h10"/>',
  back: '<path d="M9.8 3.4 5.2 8l4.6 4.6"/>',
  console: '<path d="m3.4 5 3 3-3 3M8.4 11.4h4.2"/>',
  rename: '<path d="M10.6 2.8 13.2 5.4 5.8 12.8 2.8 13.2 3.2 10.2Z"/>',
  keep: '<path d="M4.4 2.4h7.2v11.2L8 11 4.4 13.6Z"/>',
  more: '<circle cx="3.5" cy="8" r=".9" fill="currentColor"/><circle cx="8" cy="8" r=".9" fill="currentColor"/><circle cx="12.5" cy="8" r=".9" fill="currentColor"/>',
};

export function icon(name) {
  const span = document.createElement("span");
  span.className = "icon";
  span.innerHTML = `<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${PATHS[name] || ""}</svg>`;
  return span;
}

// A button with an icon and, optionally, words. `kind`: primary, danger,
// ghost. An icon-only button keeps its meaning in a tooltip.
export function button({ label, icon: iconName, kind = "", title, onclick, small }) {
  const classes = ["btn", kind, small ? "small" : "", label ? "" : "square"].filter(Boolean).join(" ");

  return h("button", { class: classes, title: title || label, onclick }, [
    iconName ? icon(iconName) : null,
    label ? h("span", {}, label) : null,
  ]);
}

// ---------------- numbers ----------------

export const fmt = {
  number: (value, digits = 2) =>
    value === null || value === undefined || Number.isNaN(value) ? "—" : Number(value).toFixed(digits),

  int: (value) =>
    value === null || value === undefined ? "—" : Number(value).toLocaleString("en-US"),

  bytes: (value) => {
    if (!value) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let size = value;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
    return `${size.toFixed(size < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
  },

  ago: (seconds) => {
    if (!seconds && seconds !== 0) return "—";
    const delta = Math.max(0, Date.now() / 1000 - seconds);
    if (delta < 60) return `${Math.round(delta)}s ago`;
    if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
    return `${Math.round(delta / 86400)}d ago`;
  },
};

// ---------------- charts ----------------
// The panel's language, in chart form: hazard orange for the line you came
// to read, ice cyan and steel for the frame around it, sage for reward,
// crimson for death and penalties, yellow for a state to notice.

export const COLORS = {
  orange: "#e08b3e",
  amber: "#f0aa63",
  cyan: "#7ed4e6",
  steel: "#557584",
  sage: "#8ec4a3",
  crimson: "#c8453c",
  yellow: "#e6c34d",
  gray: "#2f3a41",
};

export const SERIES_COLORS = [
  "#e08b3e", "#7ed4e6", "#8ec4a3", "#e6c34d", "#c8453c",
  "#f0aa63", "#7f9aa8", "#b6a8e0", "#a5d6ff", "#e8cba6",
];

// Grid, axis lines and labels: cold and quiet, so the series are the only
// thing with colour in the box.
export const CHART_INK = {
  label: "#93a2ab",
  axis: "#303334",
  split: "#26292a",
  name: "#7ed4e6",
};

// Every axis in the panel is named: a chart that does not say what its
// numbers are is a picture, not a measurement. `name` on an axis of this
// base lands under the x axis and along the y axis by itself.
export function chartBase() {
  const name = { color: CHART_INK.name, fontSize: 10, fontFamily: "ui-monospace, SF Mono, Menlo, monospace" };

  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: CHART_INK.label, fontFamily: "ui-monospace, SF Mono, Menlo, monospace", fontSize: 11 },
    grid: { left: 64, right: 26, top: 34, bottom: 52 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#232526",
      borderColor: "#3d4042",
      borderWidth: 1,
      textStyle: { color: "#e7ecef", fontSize: 11 },
      axisPointer: { lineStyle: { color: "#4c5052" } },
    },
    legend: {
      top: 6,
      right: 10,
      icon: "roundRect",
      itemWidth: 12,
      itemHeight: 3,
      textStyle: { color: CHART_INK.label, fontSize: 11 },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: name,
      axisLine: { lineStyle: { color: CHART_INK.axis } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      nameLocation: "middle",
      nameGap: 48,
      nameTextStyle: name,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: CHART_INK.split } },
    },
  };
}

export function line(name, data, color, extra = {}) {
  return {
    name,
    type: "line",
    data,
    smooth: 0.15,
    symbol: "none",
    lineStyle: { width: 1.7, color },
    itemStyle: { color },
    ...extra,
  };
}

// A chart that follows the size of its box, and lets go of its canvas
// when the page it lives on is left.
export function chartIn(node) {
  const chart = echarts.init(node, null, { renderer: "canvas" });
  const observer = new ResizeObserver(() => chart.resize());
  observer.observe(node);
  cleanup(() => { observer.disconnect(); chart.dispose(); });
  return chart;
}

// ---------------- page lifetime ----------------
// Whatever a page starts - timers, streams, charts - is registered here
// and stopped when the page is left, so nothing keeps polling behind the
// next one.

let disposers = [];

export function cleanup(fn) { disposers.push(fn); }

export function leavePage() {
  for (const dispose of disposers) {
    try { dispose(); } catch { /* a page on its way out */ }
  }
  disposers = [];
}

// Redraws that do not throw away where the reader was.
//
// A list that rebuilds itself every couple of seconds takes the scroll
// position with it: the page jumps back the moment you scroll down, and a
// wide table can never be scrolled sideways at all. So a refresh only
// redraws when something actually changed, and puts the scroll back where
// it was afterwards.
export function redraw(node, signature, build) {
  if (node.dataset.signature === signature) return false;

  const page = document.getElementById("view").parentElement;
  const top = page.scrollTop;
  const sideways = [...node.querySelectorAll(".table-scroll")].map((box) => box.scrollLeft);

  node.replaceChildren(...[].concat(build()));
  node.dataset.signature = signature;

  page.scrollTop = top;
  [...node.querySelectorAll(".table-scroll")].forEach((box, index) => {
    box.scrollLeft = sideways[index] ?? 0;
  });

  return true;
}

// Text that follows the tail unless the reader has scrolled up to read.
export function setText(node, text) {
  const atBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 8;
  const top = node.scrollTop;

  node.textContent = text;
  node.scrollTop = atBottom ? node.scrollHeight : top;
}

export function every(ms, fn) {
  const timer = setInterval(fn, ms);
  cleanup(() => clearInterval(timer));
}

// ---------------- modal ----------------

// A "more" button that opens a short list of actions under itself - for
// the things a row can do that do not all fit on the row.
// items: [{ label, icon, danger, onclick }], null entries are skipped.
export function menu(items) {
  const trigger = button({ icon: "more", small: true, title: "More" });

  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    document.querySelector(".menu")?.remove();

    const list = h("div", { class: "menu" }, items.filter(Boolean).map((item) =>
      h("button", {
        class: `menu-item ${item.danger ? "danger" : ""}`,
        onclick: (click) => { click.stopPropagation(); list.remove(); item.onclick(); },
      }, [item.icon ? icon(item.icon) : null, h("span", {}, item.label)])));

    document.body.append(list);

    // Under the button, right edges aligned, kept inside the window.
    const box = trigger.getBoundingClientRect();
    list.style.top = `${Math.min(box.bottom + 4, window.innerHeight - list.offsetHeight - 8)}px`;
    list.style.left = `${Math.max(8, box.right - list.offsetWidth)}px`;

    const close = (other) => {
      if (other.type === "keydown" && other.key !== "Escape") return;
      list.remove();
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", close);
    };

    setTimeout(() => {
      document.addEventListener("click", close);
      document.addEventListener("keydown", close);
    }, 0);
  });

  return trigger;
}

// A popup the size of a page: what a family tree opens when a node is
// clicked. It is the same overlay the questions use, so Escape, the
// backdrop and the close button all end it the same way.
export function popup({ title, body, note }) {
  const backdrop = document.getElementById("modal-backdrop");
  const box = document.getElementById("modal");

  const close = () => {
    backdrop.hidden = true;
    // A popup can hold charts, and a chart holds a canvas until it is told
    // to let go of it.
    for (const canvas of box.querySelectorAll(".chart")) {
      echarts.getInstanceByDom(canvas)?.dispose();
    }

    box.className = "modal";
    box.replaceChildren();
    document.removeEventListener("keydown", onKey);
  };

  const onKey = (event) => { if (event.key === "Escape") close(); };

  box.className = "modal big";
  box.replaceChildren(
    h("header", {}, [
      h("span", {}, title),
      note ? h("span", { class: "note" }, note) : null,
      h("span", { class: "spacer" }),
      button({ label: "Close", kind: "ghost", small: true, onclick: close }),
    ]),
    h("div", { class: "body scroller" }, body),
  );

  backdrop.hidden = false;
  backdrop.onclick = (event) => { if (event.target === backdrop) close(); };
  document.addEventListener("keydown", onKey);

  return { close, fill: (content) => box.querySelector(".body").replaceChildren(content) };
}

export function modal({ title, body, confirm, danger, onConfirm }) {
  const backdrop = document.getElementById("modal-backdrop");
  const box = document.getElementById("modal");

  const close = () => { backdrop.hidden = true; box.replaceChildren(); };

  box.className = "modal";
  const error = h("div", { class: "error" });

  const confirmButton = button({
    label: confirm || "Confirm",
    kind: danger ? "danger solid" : "primary",
    onclick: async () => {
      confirmButton.disabled = true;
      try { await onConfirm(); close(); }
      catch (failure) { confirmButton.disabled = false; error.textContent = failure.message; }
    },
  });

  box.replaceChildren(
    h("header", {}, title),
    h("div", { class: "body" }, [body, error]),
    h("footer", {}, [button({ label: "Cancel", kind: "ghost", onclick: close }), confirmButton]),
  );

  backdrop.hidden = false;
  backdrop.onclick = (event) => { if (event.target === backdrop) close(); };
}

// ---------------- small widgets ----------------

// A row of buttons of which exactly one is on - for choices you should be
// able to see all at once instead of opening a dropdown to find.
export function segmented(options, value, onchange) {
  const root = h("div", { class: "segmented" });

  const draw = (current) => {
    root.replaceChildren(...options.map(([key, text]) =>
      h("button", {
        class: key === current ? "on" : "",
        onclick: () => { draw(key); onchange(key); },
      }, text)));
  };

  draw(value);
  return root;
}

// A row of chips of which exactly one is on: the same choice a segmented
// control makes, in the shape that fits inside a panel header.
export function chips(options, value, onchange) {
  const box = h("div", { class: "row", style: "gap:4px;flex-wrap:nowrap" });

  const draw = (current) => {
    box.replaceChildren(...options.map(([key, text, title]) =>
      h("button", {
        class: `chip ${key === current ? "on" : ""}`,
        style: "margin:0",
        title: title || null,
        onclick: () => { draw(key); onchange(key); },
      }, text)));
  };

  draw(value);
  return box;
}

// Chips where ANY NUMBER can be on at once - for a chart that draws one
// line, or two, or all of them. The last one on cannot be switched off:
// an empty chart answers no question at all.
export function toggles(options, selected, onchange) {
  const box = h("div", { class: "row", style: "gap:4px;flex-wrap:nowrap" });

  const draw = () => {
    box.replaceChildren(...options.map(([key, text, title]) =>
      h("button", {
        class: `chip ${selected.has(key) ? "on" : ""}`,
        style: "margin:0",
        title: title || null,
        onclick: () => {
          if (selected.has(key)) {
            if (selected.size === 1) return;
            selected.delete(key);
          } else {
            selected.add(key);
          }

          draw();
          onchange(selected);
        },
      }, text)));
  };

  draw();
  return box;
}

export function toggle(checked, onchange) {
  const input = h("input", { type: "checkbox", class: "switch", checked });
  input.addEventListener("change", () => onchange(input.checked));
  return input;
}
