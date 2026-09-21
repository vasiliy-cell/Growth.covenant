// Comparing runs, in three steps: pick the runs, pick what to compare them
// on, look at the charts. Each step has its own address, so the browser's
// back button walks back through them.

import { api, h, fmt, button, go, route, chartBase, chartIn, SERIES_COLORS } from "../lib.js";

// What has been picked so far, kept across the three steps and across a
// reload of the page.
const saved = JSON.parse(sessionStorage.getItem("compare") || "{}");

const state = {
  runs: saved.runs || [],
  metrics: saved.metrics || ["shaped_reward"],
  smoothing: saved.smoothing || 5,
};

function remember() {
  sessionStorage.setItem("compare", JSON.stringify(state));
}

export async function comparePage(root, step) {
  const [{ worlds }, metrics] = await Promise.all([api.worlds(), api.metrics()]);

  // A run deleted since it was picked is quietly dropped from the pick.
  const known = new Set(worlds.map((world) => world.id));
  state.runs = state.runs.filter((id) => known.has(id));
  remember();

  if (step !== "runs" && !state.runs.length) return go(route.compare());
  if (step === "charts" && !state.metrics.length) return go(route.compare("metrics"));

  const page = h("div", { class: "page" }, [stepper(step)]);
  root.replaceChildren(page);

  if (step === "runs") page.append(...pickRuns(worlds));
  if (step === "metrics") page.append(...pickMetrics(metrics));
  if (step === "charts") page.append(...(await charts(worlds, metrics)));
}

// ---------------- the three steps ----------------

function stepper(current) {
  const steps = [["runs", "Runs"], ["metrics", "Metrics"], ["charts", "Charts"]];
  const at = steps.findIndex(([key]) => key === current);

  return h("div", { class: "stepper" }, steps.map(([key, text], index) => h("a", {
    class: `step ${index === at ? "on" : ""} ${index < at ? "done" : ""}`,
    href: index < at ? route.compare(key === "runs" ? "" : key) : null,
  }, [h("span", { class: "number" }, index + 1), text])));
}

function pickRuns(worlds) {
  const count = h("span", { class: "sub" });
  const list = h("div", {});

  const next = button({
    label: "Done",
    icon: "resume",
    kind: "primary",
    onclick: () => go(route.compare("metrics")),
  });

  const draw = () => {
    count.textContent = `${state.runs.length} of ${worlds.length} picked`;
    next.disabled = !state.runs.length;

    list.replaceChildren(...worlds.map((world) => {
      const on = state.runs.includes(world.id);

      return h("div", {
        class: `pick ${on ? "on" : ""}`,
        onclick: () => {
          state.runs = on ? state.runs.filter((id) => id !== world.id) : [...state.runs, world.id];
          remember();
          draw();
        },
      }, [
        h("span", { class: "box" }),
        h("div", { style: "min-width:0;flex:1" }, [
          h("div", { class: "name" }, world.label || world.world_id),
          h("div", { class: "meta" }, `${world.world_id} · ${fmt.ago(world.created_at)}`),
        ]),
        h("span", { class: "badge" }, world.species || "—"),
        h("span", { class: "meta", style: "width:90px;text-align:right" }, `seed ${world.seeds[0] ?? "—"}`),
        h("span", { class: "meta", style: "width:90px;text-align:right" }, `${fmt.int(world.episodes)} episodes`),
      ]);
    }));
  };

  draw();

  return [
    h("div", { class: "page-head" }, [
      h("h1", {}, "Which runs?"),
      count,
      h("span", { class: "spacer" }),
      button({ label: "All", kind: "ghost", onclick: () => { state.runs = worlds.map((w) => w.id); remember(); draw(); } }),
      button({ label: "None", kind: "ghost", onclick: () => { state.runs = []; remember(); draw(); } }),
      next,
    ]),
    h("div", { class: "panel" }, list),
  ];
}

function pickMetrics(metrics) {
  const grid = h("div", { class: "cards" });

  const next = button({
    label: "Show charts",
    icon: "resume",
    kind: "primary",
    onclick: () => go(route.compare("charts")),
  });

  const draw = () => {
    next.disabled = !state.metrics.length;

    grid.replaceChildren(...Object.entries(metrics).map(([key, metric]) => {
      const on = state.metrics.includes(key);

      return h("div", {
        class: `card-pick ${on ? "on" : ""}`,
        onclick: () => {
          state.metrics = on ? state.metrics.filter((m) => m !== key) : [...state.metrics, key];
          remember();
          draw();
        },
      }, [
        h("div", { class: "row", style: "flex-wrap:nowrap" }, [
          h("span", { class: "box" }),
          h("span", { class: "title" }, metric.name),
        ]),
        h("div", { class: "hint" }, metric.description),
        h("div", { class: "meta" }, metric.higher_is_better ? "higher is better" : "lower is better"),
      ]);
    }));
  };

  draw();

  return [
    h("div", { class: "page-head" }, [
      h("h1", {}, "Compare them on what?"),
      h("span", { class: "sub" }, `${state.runs.length} runs · pick one or several`),
      h("span", { class: "spacer" }),
      button({ label: "Runs", icon: "back", kind: "ghost", onclick: () => go(route.compare()) }),
      next,
    ]),
    grid,
  ];
}

async function charts(worlds, metrics) {
  const byId = new Map(worlds.map((world) => [world.id, world]));

  // One colour per run, the same on every chart, so a run is recognised
  // at a glance from one chart to the next.
  const color = (id) => SERIES_COLORS[state.runs.indexOf(id) % SERIES_COLORS.length];

  const results = await Promise.all(state.metrics.map((metric) => api.compare(state.runs, metric)));

  const smoothing = h("div", { class: "row", style: "gap:0" }, [1, 5, 20, 50].map((size) =>
    h("span", {
      class: `chip ${size === state.smoothing ? "on" : ""}`,
      style: "margin:0 4px 0 0",
      // Same address, new smoothing: ask the router to draw this step again.
      onclick: () => { state.smoothing = size; remember(); window.dispatchEvent(new HashChangeEvent("hashchange")); },
    }, size === 1 ? "raw" : `smooth ${size}`)));

  const legend = h("div", { class: "panel" }, h("div", { class: "body legend" },
    state.runs.map((id) => h("span", { class: "legend-item" }, [
      h("span", { class: "swatch", style: `background:${color(id)}` }),
      (byId.get(id)?.label || byId.get(id)?.world_id || id),
      h("span", { class: "dim mono" }, ` · seed ${byId.get(id)?.seeds[0] ?? "—"}`),
    ]))));

  const blocks = results.map((result) => {
    const node = h("div", { class: "chart" });

    requestAnimationFrame(() => drawChart(chartIn(node), result, state.smoothing, color));

    return h("div", { class: "panel" }, [
      h("header", {}, [result.name, h("span", { class: "note" }, result.description)]),
      h("div", { class: "body" }, node),
      table(result, color),
    ]);
  });

  return [
    h("div", { class: "page-head" }, [
      h("h1", {}, "Charts"),
      h("span", { class: "sub" }, `${state.runs.length} runs · ${state.metrics.length} metrics`),
      h("span", { class: "spacer" }),
      smoothing,
      button({ label: "Metrics", icon: "back", kind: "ghost", onclick: () => go(route.compare("metrics")) }),
      button({ label: "Runs", icon: "back", kind: "ghost", onclick: () => go(route.compare()) }),
    ]),
    legend,
    ...blocks,
  ];
}

// ---------------- chart ----------------

function smooth(values, size) {
  if (size <= 1) return values;

  const window = [];
  let sum = 0;
  let count = 0;

  return values.map((value) => {
    window.push(value);
    if (value !== null && value !== undefined) { sum += value; count += 1; }

    if (window.length > size) {
      const dropped = window.shift();
      if (dropped !== null && dropped !== undefined) { sum -= dropped; count -= 1; }
    }

    return count ? sum / count : null;
  });
}

function drawChart(chart, result, smoothing, color) {
  const base = chartBase();

  chart.setOption({
    ...base,
    legend: { show: false },
    grid: { ...base.grid, top: 20 },
    dataZoom: [{ type: "inside" }],
    xAxis: { ...base.xAxis, type: "value", name: "episode", nameTextStyle: { color: "#62626c" } },
    yAxis: { ...base.yAxis },
    series: result.series.map((series) => {
      const values = smooth(series.values, smoothing);

      return {
        name: `${series.label} · seed ${series.seed ?? "—"}`,
        type: "line",
        symbol: "none",
        smooth: 0.2,
        lineStyle: { width: 1.8, color: color(series.id) },
        itemStyle: { color: color(series.id) },
        data: series.episodes.map((episode, index) => [episode, values[index]]),
      };
    }),
  });
}

// ---------------- the numbers under a chart ----------------

function table(result, color) {
  // Every run starts as the same clueless newborn, so the run is judged by
  // where it ended up: the average over its last tenth of episodes.
  const rows = result.series.map((series) => {
    const present = series.values.filter((value) => value !== null && value !== undefined);
    const tail = present.slice(-Math.max(1, Math.floor(present.length / 10)));

    return {
      series,
      end: tail.length ? tail.reduce((sum, value) => sum + value, 0) / tail.length : null,
      best: present.length ? (result.higher_is_better ? Math.max(...present) : Math.min(...present)) : null,
      last: present.length ? present[present.length - 1] : null,
    };
  });

  rows.sort((a, b) => {
    if (a.end === null) return 1;
    if (b.end === null) return -1;
    return result.higher_is_better ? b.end - a.end : a.end - b.end;
  });

  return h("table", {}, [
    h("thead", {}, h("tr", {}, [
      h("th", { style: "width:36px" }, "#"),
      h("th", {}, "Run"),
      h("th", { class: "num" }, "Episodes"),
      h("th", { class: "num", title: "average over the last 10% of the run's episodes" }, `${result.name}, end of run`),
      h("th", { class: "num", title: "the best single episode" }, "best episode"),
      h("th", { class: "num", title: "the final episode" }, "last episode"),
    ])),
    h("tbody", {}, rows.map((row, index) => h("tr", {}, [
      h("td", { class: "mono", style: index === 0 ? "color:var(--accent);font-weight:700" : "color:var(--dim)" }, index + 1),
      h("td", {}, h("span", { class: "row", style: "flex-wrap:nowrap" }, [
        h("span", { class: "swatch", style: `background:${color(row.series.id)}` }),
        row.series.label,
        h("span", { class: "dim mono", style: "font-size:11px" }, `seed ${row.series.seed ?? "—"}`),
      ])),
      h("td", { class: "num" }, fmt.int(row.series.episodes.length)),
      h("td", { class: "num accent" }, fmt.number(row.end, 2)),
      h("td", { class: "num" }, fmt.number(row.best, 2)),
      h("td", { class: "num" }, fmt.number(row.last, 2)),
    ]))),
  ]);
}
