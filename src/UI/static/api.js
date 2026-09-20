// Everything the panel knows about the server, in one place.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `${response.status} ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  worlds: () => request("/api/worlds"),
  details: (id) => request(`/api/worlds/${encodeURI(id)}/details`),
  rewards: (id) => request(`/api/worlds/${encodeURI(id)}/rewards`),
  learning: (id) => request(`/api/worlds/${encodeURI(id)}/learning`),
  family: (id) => request(`/api/worlds/${encodeURI(id)}/family`),

  archive: (id, note, remove) =>
    request(`/api/worlds/${encodeURI(id)}/archive`, {
      method: "POST",
      body: JSON.stringify({ note, delete: remove }),
    }),

  remove: (id) => request(`/api/worlds/${encodeURI(id)}`, { method: "DELETE" }),

  live: () => request("/api/live"),
  runs: () => request("/api/runs"),
  launch: (body) => request("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  stop: (id) => request(`/api/runs/${id}`, { method: "DELETE" }),
  console: (id) => request(`/api/runs/${id}/console`),
  clear: () => request("/api/runs/clear", { method: "POST" }),
  parallel: (n) => request("/api/parallel", { method: "POST", body: JSON.stringify({ parallel: n }) }),
  config: () => request("/api/config"),
};

// ---------------- small helpers every view wants ----------------

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

export const fmt = {
  number: (value, digits = 2) =>
    value === null || value === undefined ? "—" : Number(value).toFixed(digits),

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

  time: (seconds) => {
    if (!seconds) return "—";
    return new Date(seconds * 1000).toLocaleString("en-GB", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
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

// The one chart theme, so every chart in the panel is the same chart.
export const CHART_COLORS = {
  cyan: "#22d3ee",
  lime: "#a3e635",
  magenta: "#f472b6",
  amber: "#fbbf24",
  red: "#fb7185",
  violet: "#a78bfa",
};

export function chartBase(extra = {}) {
  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: "#868e9e", fontFamily: "ui-monospace, SF Mono, Menlo, monospace", fontSize: 11 },
    grid: { left: 54, right: 20, top: 34, bottom: 34, ...(extra.grid || {}) },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#0d1014",
      borderColor: "#323843",
      borderWidth: 1,
      textStyle: { color: "#e7eaf0", fontSize: 11 },
      axisPointer: { lineStyle: { color: "#323843" } },
    },
    legend: {
      top: 4,
      right: 8,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 3,
      textStyle: { color: "#868e9e", fontSize: 11 },
      ...(extra.legend || {}),
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#23272f" } },
      axisTick: { show: false },
      splitLine: { show: false },
      ...(extra.xAxis || {}),
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#1a1e25" } },
      ...(extra.yAxis || {}),
    },
  };
}

export function modal({ title, body, confirm, danger, onConfirm }) {
  const backdrop = document.getElementById("modal-backdrop");
  const box = document.getElementById("modal");

  const close = () => { backdrop.hidden = true; box.replaceChildren(); };

  const confirmButton = h("button", {
    class: danger ? "danger" : "accent",
    onclick: async () => {
      confirmButton.disabled = true;
      try { await onConfirm(box); close(); }
      catch (error) { confirmButton.disabled = false; box.querySelector(".error").textContent = error.message; }
    },
  }, confirm || "Confirm");

  box.replaceChildren(
    h("header", {}, title),
    h("div", { class: "body" }, [body, h("div", { class: "error muted", style: "margin-top:10px;color:#fb7185" })]),
    h("footer", {}, [h("button", { class: "ghost", onclick: close }, "Cancel"), confirmButton]),
  );

  backdrop.hidden = false;
  backdrop.onclick = (event) => { if (event.target === backdrop) close(); };
}
