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

export const api = {
  worlds: () => request("/api/worlds"),
  facets: () => request("/api/facets"),
  metrics: () => request("/api/metrics"),
  config: () => request("/api/config"),

  details: (id) => request(world(id, "details")),
  rewards: (id) => request(world(id, "rewards")),
  learning: (id) => request(world(id, "learning")),
  family: (id) => request(world(id, "family")),
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
  dice: '<rect x="2.4" y="2.4" width="11.2" height="11.2" rx="2.4"/><circle cx="5.6" cy="5.6" r=".6" fill="currentColor"/><circle cx="10.4" cy="10.4" r=".6" fill="currentColor"/><circle cx="8" cy="8" r=".6" fill="currentColor"/>',
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
// Orange leads; the other colours are GitHub's dark palette, chosen to
// stay apart from each other on black.

export const COLORS = {
  orange: "#f0883e",
  gold: "#e3b341",
  rose: "#ff7b72",
  blue: "#79c0ff",
  green: "#3fb950",
  red: "#f85149",
  purple: "#d2a8ff",
  gray: "#3a3a42",
};

export const SERIES_COLORS = [
  "#f0883e", "#79c0ff", "#e3b341", "#ff7b72", "#3fb950",
  "#d2a8ff", "#ffa657", "#56d4dd", "#a5d6ff", "#ffc680",
];

export function chartBase() {
  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: "#9d9da8", fontFamily: "ui-monospace, SF Mono, Menlo, monospace", fontSize: 11 },
    grid: { left: 56, right: 22, top: 36, bottom: 36 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#131316",
      borderColor: "#34343b",
      borderWidth: 1,
      textStyle: { color: "#ededf0", fontSize: 11 },
      axisPointer: { lineStyle: { color: "#4a4a53" } },
    },
    legend: {
      top: 6,
      right: 10,
      icon: "roundRect",
      itemWidth: 12,
      itemHeight: 3,
      textStyle: { color: "#9d9da8", fontSize: 11 },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#26262b" } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#1b1b1f" } },
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

export function modal({ title, body, confirm, danger, onConfirm }) {
  const backdrop = document.getElementById("modal-backdrop");
  const box = document.getElementById("modal");

  const close = () => { backdrop.hidden = true; box.replaceChildren(); };
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

export function toggle(checked, onchange) {
  const input = h("input", { type: "checkbox", class: "switch", checked });
  input.addEventListener("change", () => onchange(input.checked));
  return input;
}
