// One place for a run: the world as it is now, and every chart of it.
//
// The same view serves a world opened from the table and the run just
// started on the Launch page - a run is not a different kind of thing while
// it is alive, it only has a live map above its charts. There is no separate
// charts page to go and find.
//
// While a run is going the charts read themselves again every so many STEPS
// of that run, not every so many seconds: one knob, in the run's own time.

import {
  api, h, fmt, button, chips, popup, chartBase, chartIn, line, COLORS,
  CHART_INK, cleanup,
} from "../lib.js";
import { liveStage } from "./live.js";

// All charts of one run move together: a range picked on one is the range
// every other one shows.
const GROUP = "run-charts";

const COHORTS = [
  ["all", "everyone"],
  ["child", "children", "while an agent is still immortal: before max_childhood_steps, or before its first child"],
  ["adult", "adults", "after childhood ended - by the clock or by breeding"],
];

const REFRESH = [[0, "off"], [200, "200"], [1000, "1000"], [5000, "5000"]];

export async function runView(node, worldId, { live = false } = {}) {
  const filter = { cohort: "all", min_steps: null, max_steps: null };
  const view = { mode: "agent", heat: "recent", onlyParents: true, refresh: 1000 };

  const charts = {};
  const state = {};

  const rewardNode = h("div", { class: "chart tall" });
  const learningNode = h("div", { class: "chart" });
  const populationNode = h("div", { class: "chart" });
  const heatNode = h("div", { class: "chart tall" });
  const treeNode = h("div", { class: "tree" });
  const treeNote = h("span", { class: "note" });
  const statsNode = h("div", { class: "body" });
  const filterNote = h("span", { class: "note" });

  const reload = async () => {
    const [rewards, learning] = await Promise.all([
      api.rewards(worldId, filter),
      api.learning(worldId, filter),
    ]);

    state.rewards = rewards;
    state.learning = learning;

    drawRewards(charts, rewardNode, rewards, view);
    drawLearning(charts, learningNode, learning);
    drawPopulation(charts, populationNode, rewards);

    filterNote.textContent = rewards.filtered
      ? `${rewards.agents.reduce((sum, value) => sum + value, 0)} agent-windows kept`
      : "the whole population";
  };

  const reloadWorld = async () => {
    const [details, family, heat] = await Promise.all([
      api.details(worldId), api.family(worldId), api.heatmap(worldId),
    ]);

    state.details = details;
    state.heat = heat;

    statsNode.replaceChildren(...runStats(details, family));
    drawHeatmap(charts, heatNode, heat, view.heat);

    if (!state.family || state.family.nodes.length !== family.nodes.length) {
      state.family = family;
      drawTree(treeNode, treeNote, family, worldId, view);
    }
  };

  // ---------------- the page ----------------

  const parts = [];

  if (live) {
    // The live map drives the refresh: every frame says which step the run
    // is on, and the charts are read again once enough of them have passed.
    let drawnAt = null;

    parts.push(liveStage(worldId, {
      onFrame: (frame) => {
        if (!view.refresh) return;
        if (drawnAt !== null && frame.step - drawnAt < view.refresh) return;

        drawnAt = frame.step;
        reload().catch(() => {});
        reloadWorld().catch(() => {});
      },
    }));
  }

  parts.push(h("div", { class: "panel" }, [
    h("header", {}, ["This run", h("span", { class: "note" }, worldId)]),
    statsNode,
  ]));

  parts.push(filterPanel(filter, view, live, filterNote, async () => {
    await reload();
  }));

  parts.push(h("div", { class: "panel" }, [
    h("header", {}, [
      "Reward per episode",
      h("span", { class: "note" }, "env · curiosity · what the networks learned from"),
      h("span", { class: "spacer" }),
      chips([["agent", "per agent"], ["total", "total"]], view.mode, (mode) => {
        view.mode = mode;
        drawRewards(charts, rewardNode, state.rewards, view);
      }),
    ]),
    h("div", { class: "body" }, rewardNode),
  ]));

  parts.push(h("div", { class: "grid-2" }, [
    h("div", { class: "panel" }, [
      h("header", {}, ["Learning", h("span", { class: "note" }, "mean per episode")]),
      h("div", { class: "body" }, learningNode),
    ]),
    h("div", { class: "panel" }, [
      h("header", {}, ["Population", h("span", { class: "note" }, "agents · births · deaths")]),
      h("div", { class: "body" }, populationNode),
    ]),
  ]));

  parts.push(h("div", { class: "panel" }, [
    h("header", {}, [
      "Where the agents are",
      h("span", { class: "note" }, "snapshots of a body on a cell"),
      h("span", { class: "spacer" }),
      chips([["recent", "recently"], ["all", "whole run"]], view.heat, (mode) => {
        view.heat = mode;
        drawHeatmap(charts, heatNode, state.heat, mode);
      }),
    ]),
    h("div", { class: "body" }, heatNode),
  ]));

  parts.push(h("div", { class: "panel" }, [
    h("header", {}, [
      "Family tree",
      treeNote,
      h("span", { class: "spacer" }),
      chips([["parents", "with offspring"], ["everyone", "everyone"]], "parents", (which) => {
        view.onlyParents = which === "parents";
        drawTree(treeNode, treeNote, state.family, worldId, view);
      }),
      button({
        label: "Fit", small: true, title: "Fit the whole tree in the box",
        onclick: () => treeNode.fitTree && treeNode.fitTree(),
      }),
    ]),
    h("div", { class: "body" }, treeNode),
  ]));

  node.replaceChildren(...parts);

  await Promise.all([reload(), reloadWorld()]);
  echarts.connect(GROUP);
}

// ---------------- what this run is ----------------

function runStats(details, family) {
  const sessions = details.sessions || [];
  const alive = family.nodes.filter((agent) => agent.alive).length;

  return [
    h("div", { class: "stats" }, [
      stat("episodes", fmt.int(details.counts.episodes)),
      stat("steps", fmt.int(sessions.length ? sessions[sessions.length - 1].to_step : 0)),
      stat("agents now", fmt.int(alive)),
      stat("agents ever", fmt.int(family.nodes.length)),
      stat("deaths", fmt.int(details.counts.deaths), "bad"),
      stat("updates", fmt.int(details.counts.updates)),
      stat("seed", sessions[0]?.seed ?? "—"),
    ]),
    h("div", { class: "mono dim", style: "font-size:11px;margin-top:10px;line-height:1.7" }, [
      `${details.species} · commit ${(details.commit || "—").slice(0, 10)} · episode = ${details.episode_length} steps`,
      ...sessions.map((session) => h("div", {},
        `session ${session.session}: steps ${session.from_step ?? "—"}–${session.to_step ?? "—"}, ` +
        `episodes ${session.from_episode ?? "—"}–${session.to_episode ?? "—"}` +
        (session.resumed_from ? ` · continued from ${session.resumed_from}` : ""))),
    ]),
  ];
}

function stat(name, value, tone = "") {
  return h("div", { class: "stat" }, [
    h("div", { class: "name" }, name),
    h("div", { class: `value ${tone}` }, value),
  ]);
}

// ---------------- who the charts are about ----------------

function filterPanel(filter, view, live, note, apply) {
  const min = h("input", { type: "number", min: "0", placeholder: "from", value: "" });
  const max = h("input", { type: "number", min: "0", placeholder: "to", value: "" });

  const use = async () => {
    filter.min_steps = min.value === "" ? null : Number(min.value);
    filter.max_steps = max.value === "" ? null : Number(max.value);
    await apply();
  };

  min.addEventListener("change", use);
  max.addEventListener("change", use);

  return h("div", { class: "panel" }, [
    h("header", {}, ["Who these charts are about", note]),
    h("div", { class: "body row", style: "gap:18px" }, [
      h("div", { class: "row", style: "gap:8px" }, [
        h("span", { class: "dim mono", style: "font-size:11px" }, "period"),
        chips(COHORTS, filter.cohort, async (cohort) => {
          filter.cohort = cohort;
          await apply();
        }),
      ]),
      h("div", { class: "row", style: "gap:8px" }, [
        h("span", { class: "dim mono", style: "font-size:11px" }, "steps lived"),
        h("div", { style: "width:96px" }, min),
        h("div", { style: "width:96px" }, max),
      ]),
      live
        ? h("div", { class: "row", style: "gap:8px" }, [
          h("span", { class: "dim mono", style: "font-size:11px" }, "redraw every"),
          chips(REFRESH, view.refresh, (value) => { view.refresh = value; }),
          h("span", { class: "dim mono", style: "font-size:11px" }, "steps"),
        ])
        : null,
    ]),
  ]);
}

// ---------------- reward ----------------
// A sum over a population that grows says nothing about whether the agents
// got better at anything: twice as many mouths earn twice as much while
// each one stays as hungry as before.

function perAgent(values, agents) {
  return values.map((value, index) => (agents[index] ? value / agents[index] : null));
}

function rewardSeries(rewards, view) {
  const scale = (values) => (view.mode === "agent" ? perAgent(values, rewards.agents) : values);

  return [
    line("shaped", scale(rewards.shaped), COLORS.orange, {
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(224,139,62,.22)" },
          { offset: 1, color: "rgba(224,139,62,0)" },
        ]),
      },
    }),
    line("env", scale(rewards.env), COLORS.sage),
    line("curiosity", scale(rewards.intrinsic), COLORS.cyan),
  ];
}

function drawRewards(charts, node, rewards, view) {
  if (!rewards) return;

  const base = chartBase();
  const chart = charts.reward || chartIn(node);

  if (!charts.reward) {
    charts.reward = chart;
    chart.group = GROUP;
  }

  chart.setOption({
    ...base,
    grid: { ...base.grid, bottom: 86 },
    dataZoom: [
      { type: "inside" },
      {
        type: "slider",
        height: 20,
        bottom: 16,
        borderColor: "#26282b",
        backgroundColor: "#101113",
        fillerColor: "rgba(224,139,62,.14)",
        dataBackground: { lineStyle: { color: "#3a3d40" }, areaStyle: { color: "#1b1d1f" } },
        selectedDataBackground: { lineStyle: { color: COLORS.orange }, areaStyle: { color: "rgba(224,139,62,.2)" } },
        handleStyle: { color: COLORS.orange, borderColor: "#a25f22" },
        moveHandleStyle: { color: "#34373a" },
        textStyle: { color: CHART_INK.label },
      },
    ],
    xAxis: { ...base.xAxis, data: rewards.episodes, name: "episode" },
    yAxis: {
      ...base.yAxis,
      name: view.mode === "agent" ? "reward per agent per episode" : "reward per episode, whole population",
    },
    series: rewardSeries(rewards, view),
  });
}

function drawLearning(charts, node, learning) {
  if (!learning) return;

  const base = chartBase();
  const chart = charts.learning || chartIn(node);

  if (!charts.learning) {
    charts.learning = chart;
    chart.group = GROUP;
  }

  chart.setOption({
    ...base,
    dataZoom: [{ type: "inside" }],
    grid: { ...base.grid, right: 64 },
    xAxis: { ...base.xAxis, data: learning.episodes, name: "episode" },
    yAxis: [
      { ...base.yAxis, name: "loss" },
      { ...base.yAxis, name: "|td error|", position: "right", nameGap: 44, splitLine: { show: false } },
    ],
    series: [
      line("loss", learning.loss, COLORS.orange),
      line("|td error|", learning.td_error, COLORS.yellow, { yAxisIndex: 1 }),
    ],
  });
}

function drawPopulation(charts, node, rewards) {
  if (!rewards) return;

  const base = chartBase();
  const chart = charts.population || chartIn(node);

  if (!charts.population) {
    charts.population = chart;
    chart.group = GROUP;
  }

  chart.setOption({
    ...base,
    dataZoom: [{ type: "inside" }],
    xAxis: { ...base.xAxis, data: rewards.episodes, name: "episode" },
    yAxis: { ...base.yAxis, name: "agents alive · births · deaths" },
    series: [
      line("agents", rewards.agents, COLORS.orange, { areaStyle: { color: "rgba(224,139,62,.1)" } }),
      { name: "births", type: "bar", data: rewards.births, itemStyle: { color: COLORS.sage }, barMaxWidth: 6 },
      { name: "deaths", type: "bar", data: rewards.deaths, itemStyle: { color: COLORS.crimson }, barMaxWidth: 6 },
    ],
  });
}

// ---------------- where the agents are ----------------
// One hue, dark to bright: a heat map answers "how much", and a rainbow
// would turn an amount into four different-looking things. The map is drawn
// the way the world is watched live - y downwards, (0,0) top left.

const HEAT_COLORS = ["#1b1d1f", "#2c2a22", "#5e4222", "#a2652b", "#e08b3e", "#f3c795"];

export function heatOption(grid, size, { title } = {}) {
  const base = chartBase();
  const labels = Array.from({ length: size }, (_, index) => String(index));
  const data = [];
  let max = 0;
  let total = 0;

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const value = grid[y][x];
      total += value;
      if (value > max) max = value;
      data.push([x, y, value]);
    }
  }

  const axis = {
    type: "category",
    data: labels,
    nameLocation: "middle",
    nameTextStyle: base.xAxis.nameTextStyle,
    axisLine: { lineStyle: { color: CHART_INK.axis } },
    axisTick: { show: false },
    splitArea: { show: false },
    axisLabel: { interval: Math.max(1, Math.round(size / 8)) - 1, color: CHART_INK.label },
  };

  return {
    ...base,
    grid: { left: 52, right: 26, top: 14, bottom: 66 },
    legend: { show: false },
    tooltip: {
      ...base.tooltip,
      trigger: "item",
      formatter: (point) => {
        const [x, y, value] = point.data;
        const share = total ? (value / total) * 100 : 0;
        return `x ${x} · y ${y}<br/>${fmt.int(value)} ${title || "snapshots"} · ${share.toFixed(2)}% of the time`;
      },
    },
    xAxis: { ...axis, name: "x on the map", nameGap: 28 },
    yAxis: { ...axis, name: "y on the map", nameGap: 36, inverse: true },
    visualMap: {
      min: 0,
      max: Math.max(max, 1),
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 6,
      itemWidth: 10,
      itemHeight: 90,
      text: ["often", "never"],
      textStyle: { color: CHART_INK.label, fontSize: 11 },
      inRange: { color: HEAT_COLORS },
    },
    series: [{
      type: "heatmap",
      data,
      progressive: 0,
      itemStyle: { borderWidth: 0 },
      emphasis: { itemStyle: { borderColor: "#e7ecef", borderWidth: 1 } },
    }],
  };
}

function drawHeatmap(charts, node, heat, mode) {
  if (!heat || !heat.size) {
    node.replaceChildren(h("div", { class: "empty" }, "no world snapshots in this log yet"));
    return;
  }

  const chart = charts.heat || chartIn(node);
  charts.heat = chart;

  chart.setOption(heatOption(mode === "recent" ? heat.recent : heat.all, heat.size));
}

// ---------------- family tree ----------------

function drawTree(node, note, family, worldId, view) {
  node.replaceChildren();
  node.fitTree = null;

  if (!family || !family.nodes.length) {
    note.textContent = "";
    node.replaceChildren(h("div", { class: "empty" }, "No births recorded in this world."));
    return;
  }

  const byId = new Map(family.nodes.map((agent) => [agent.id, agent]));

  // One parent makes a tree, two make a graph. The tree is drawn through the
  // FIRST parent and the second one is named on the card - which keeps a
  // sexual population readable instead of turning it into a mesh.
  const entries = new Map(family.nodes.map((agent) => [agent.id, { agent, children: [] }]));
  const roots = [];

  for (const entry of entries.values()) {
    const parent = entry.agent.parents.find((parentId) => byId.has(parentId));
    if (parent) entries.get(parent).children.push(entry);
    else roots.push(entry);
  }

  // By default only the lineages that went somewhere: an agent that never
  // had a child is a dead end, and a thousand dead ends is a hedge, not a
  // tree. The toggle in the header brings everybody back.
  const prune = (entry) => ({
    ...entry,
    children: entry.children.filter((child) => child.children.length).map(prune),
  });

  const shown = view.onlyParents ? roots.filter((root) => root.children.length).map(prune) : roots;
  const hierarchy = d3.hierarchy({ agent: null, children: shown }, (item) => item.children);
  const total = hierarchy.descendants().length - 1;

  if (!total) {
    note.textContent = "";
    node.replaceChildren(h("div", { class: "empty" }, "Nobody in this world has had a child yet."));
    return;
  }

  note.textContent = `${total} of ${family.nodes.length} agents · ` +
    `${family.nodes.filter((agent) => agent.alive).length} alive · click one`;

  // nodeSize, not size: the spacing between two agents is fixed and the
  // DRAWING grows, so nodes never slide into each other however many there
  // are - the box scrolls and zooms instead.
  d3.tree().nodeSize([38, 76]).separation((a, b) => (a.parent === b.parent ? 1 : 1.4))(hierarchy);

  const nodes = hierarchy.descendants().filter((item) => item.data.agent);
  const xs = nodes.map((item) => item.x);
  const ys = nodes.map((item) => item.y);
  const box = {
    left: Math.min(...xs) - 40,
    right: Math.max(...xs) + 40,
    top: Math.min(...ys) - 30,
    bottom: Math.max(...ys) + 30,
  };

  const width = node.clientWidth || 1000;
  const height = node.clientHeight || 520;

  const svg = d3.select(node).append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  const canvas = svg.append("g");

  canvas.selectAll("path.link")
    .data(hierarchy.links().filter((link) => link.source.data.agent))
    .join("path")
    .attr("class", "link")
    .attr("d", d3.linkVertical().x((item) => item.x).y((item) => item.y));

  // The hover card lives on the body, above everything - so the tree owns
  // it and throws the old one away when it is drawn again, or a run that
  // has a child every few seconds would leave a pile of them behind.
  if (node.card) node.card.remove();

  const card = h("div", { class: "card", style: "display:none" });
  node.card = card;
  document.body.append(card);
  cleanup(() => card.remove());

  const drawn = canvas.selectAll("g.node")
    .data(nodes)
    .join("g")
    .attr("class", (item) => `node ${item.data.agent.alive ? "alive" : "dead"}`)
    .attr("transform", (item) => `translate(${item.x},${item.y})`);

  drawn.append("circle")
    .attr("r", (item) => 5 + Math.min(6, (item.data.agent.offspring || 0) * 1.5))
    .attr("fill", (item) => (item.data.agent.alive ? COLORS.orange : "#41464a"));

  drawn.append("text")
    .attr("y", -11)
    .attr("text-anchor", "middle")
    .attr("fill", CHART_INK.label)
    .style("font", "10px ui-monospace, Menlo, monospace")
    .text((item) => `#${item.data.agent.index}`);

  drawn
    .on("mousemove", (event, item) => showCard(card, event, item.data.agent))
    .on("mouseleave", () => { card.style.display = "none"; })
    .on("click", (event, item) => {
      card.style.display = "none";
      openAgent(worldId, item.data.agent);
    });

  node.addEventListener("mouseleave", () => { card.style.display = "none"; });

  // Zoom with the wheel, drag to pan - a tree of two thousand agents is
  // bigger than any box it could be drawn in.
  const zoom = d3.zoom().scaleExtent([0.08, 6]).on("zoom", (event) => {
    canvas.attr("transform", event.transform);
    // Remembered, so a birth in a running world redraws the tree without
    // yanking the view back to where it started.
    node.zoomAt = event.transform;
  });

  svg.call(zoom);

  const fit = () => {
    const scale = Math.min(1.2, width / (box.right - box.left), height / (box.bottom - box.top));
    const x = width / 2 - ((box.left + box.right) / 2) * scale;
    const y = 14 - box.top * scale;

    svg.call(zoom.transform, d3.zoomIdentity.translate(x, y).scale(scale));
  };

  node.fitTree = () => { node.zoomAt = null; fit(); };

  if (node.zoomAt) svg.call(zoom.transform, node.zoomAt);
  else fit();
}

function showCard(card, event, agent) {
  card.replaceChildren(
    h("h4", {}, `Agent #${agent.index} · ${agent.alive ? "alive" : "died"}`),
    h("div", { class: "kv" }, [
      h("span", {}, "born"), h("span", {}, `step ${fmt.int(agent.birth_step)}`),
      h("span", {}, "lifespan"), h("span", {}, agent.lifespan === null ? "—" : `${fmt.int(agent.lifespan)} ticks`),
      h("span", {}, "offspring"), h("span", {}, agent.offspring ?? "—"),
      h("span", {}, "death"), h("span", {}, agent.cause_of_death || "—"),
    ]),
    h("div", { class: "dim", style: "margin-top:8px" }, "click for the whole life"),
  );

  card.style.display = "block";
  card.style.left = `${Math.min(event.clientX + 16, window.innerWidth - 300)}px`;
  card.style.top = `${Math.min(event.clientY + 14, window.innerHeight - 180)}px`;
}

// ---------------- one agent, as a page-sized popup ----------------

async function openAgent(worldId, node) {
  const box = popup({
    title: `Agent #${node.index}`,
    note: node.alive ? "alive" : `died at step ${fmt.int(node.death_step)}`,
    body: h("div", { class: "empty" }, "Reading every step this agent ever took…"),
  });

  try {
    box.fill(agentBody(await api.agent(worldId, node.id)));
  } catch (error) {
    box.fill(h("div", { class: "empty" }, error.message));
  }
}

function agentBody(agent) {
  const heat = h("div", { class: "chart tall" });
  const ended = agent.bred_at !== null && agent.bred_at !== undefined
    ? `${fmt.int(agent.childhood_ended_at)} (its first child)`
    : `${fmt.int(agent.childhood_ended_at)} (the clock)`;

  const body = h("div", {}, [
    h("div", { class: "stats" }, [
      stat("born", `step ${fmt.int(agent.birth_step)}`),
      stat(agent.alive ? "alive" : "died", agent.alive ? "still walking" : `step ${fmt.int(agent.death_step)}`),
      stat("lived", `${fmt.int(agent.lifespan)} ticks`),
      stat("children", fmt.int(agent.offspring)),
      stat("childhood ended at", ended),
      stat("cause of death", agent.cause_of_death || "—"),
    ]),

    // Both rewards, both named. The gap between them is this agent's
    // curiosity, and one number called "reward" would hide which is which.
    h("div", { class: "stats", style: "margin-top:6px" }, [
      stat("reward from the world", fmt.number(agent.reward.env, 1)),
      stat("reward it learned from", fmt.number(agent.reward.shaped, 1)),
      stat("of that, curiosity", fmt.number(agent.reward.intrinsic, 1)),
      stat("parents", agent.parents.length ? agent.parents.map(shortId).join(" + ") : "founder"),
    ]),

    h("div", { class: "grid-2", style: "margin-top:6px" }, [
      h("div", { class: "panel" }, [
        h("header", {}, ["Phenotype", h("span", { class: "note" }, "what its genes were read into")]),
        h("div", { class: "body mono", style: "font-size:11px" },
          h("div", { class: "kv" }, Object.entries(agent.phenotype || {})
            .sort(([a], [b]) => a.localeCompare(b))
            .flatMap(([name, value]) => [
              h("span", { class: "muted" }, name),
              h("span", {}, fmt.number(value, Math.abs(value) >= 100 ? 0 : 4)),
            ]))),
      ]),
      h("div", { class: "panel" }, [
        h("header", {}, ["Genotype", h("span", { class: "note" }, "what it was born with")]),
        h("div", { class: "body mono", style: "font-size:11px" }, genotypeBody(agent.genotype)),
      ]),
    ]),

    h("div", { class: "panel", style: "margin-top:6px" }, [
      h("header", {}, [
        "Where this one walked",
        h("span", { class: "note" }, `${fmt.int(agent.heat.samples)} of its own steps`),
      ]),
      h("div", { class: "body" }, heat),
    ]),
  ]);

  // The chart is drawn once the popup is on screen and the box has a width.
  setTimeout(() => {
    if (!agent.heat.size) {
      heat.replaceChildren(h("div", { class: "empty" }, "no steps of this agent are in the log"));
      return;
    }

    chartIn(heat).setOption(heatOption(agent.heat.grid, agent.heat.size, { title: "ticks" }));
  }, 0);

  return body;
}

function genotypeBody(genotype) {
  if (!genotype || typeof genotype !== "object") return h("div", { class: "dim" }, "—");

  const pairs = Object.entries(genotype).filter(([, value]) => Array.isArray(value));

  // A mendel genotype is two alleles per gene; the other species keep one
  // number per gene, and both are worth seeing next to the phenotype.
  return h("div", { class: "kv" }, (pairs.length ? pairs : Object.entries(genotype))
    .sort(([a], [b]) => a.localeCompare(b))
    .flatMap(([name, value]) => [
      h("span", { class: "muted" }, name),
      h("span", {}, Array.isArray(value)
        ? value.map((allele) => (Array.isArray(allele)
          ? `${fmt.number(allele[0], Math.abs(allele[0]) >= 100 ? 0 : 3)}${allele[1]}`
          : fmt.number(allele, 3))).join("  ")
        : fmt.number(value, 3)),
    ]));
}

function shortId(agentId) {
  return `#${agentId.split("-").pop().replace(/^0+/, "") || 0}`;
}
