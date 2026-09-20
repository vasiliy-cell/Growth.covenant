// One world: what it earned, what it learned, and who descended from whom.

import { api, h, fmt, chartBase, CHART_COLORS } from "../api.js";

export async function world(root, id, { back, replay }) {
  const [details, rewards, learning, family] = await Promise.all([
    api.details(id), api.rewards(id), api.learning(id), api.family(id),
  ]);

  const rewardChart = h("div", { class: "chart" });
  const learningChart = h("div", { class: "chart" });
  const treeBox = h("div", { class: "tree" });

  root.replaceChildren(h("div", { class: "stack" }, [
    header(details, { back, replay }),
    h("div", { class: "panel" }, [
      h("header", {}, [
        "Reward per episode",
        h("span", { class: "spacer" }),
        h("span", { class: "muted mono" }, "env · curiosity · what the network learned from"),
      ]),
      h("div", { class: "body" }, rewardChart),
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "panel" }, [
        h("header", {}, ["Learning", h("span", { class: "spacer" }), h("span", { class: "muted mono" }, "mean per episode")]),
        h("div", { class: "body" }, learningChart),
      ]),
      h("div", { class: "panel" }, [
        h("header", {}, [
          "Population",
          h("span", { class: "spacer" }),
          h("span", { class: "muted mono" }, `${family.nodes.length} agents · ${family.nodes.filter((n) => n.alive).length} alive`),
        ]),
        h("div", { class: "body" }, populationChart(rewards)),
      ]),
    ]),
    h("div", { class: "panel" }, [
      h("header", {}, [
        "Family tree",
        h("span", { class: "spacer" }),
        h("span", { class: "muted mono" }, "hover a node for its genotype and phenotype"),
      ]),
      h("div", { class: "body" }, treeBox),
    ]),
  ]));

  drawRewards(rewardChart, rewards);
  drawLearning(learningChart, learning);
  drawTree(treeBox, family);
}

function header(details, { back, replay }) {
  const sessions = details.sessions || [];

  return h("div", { class: "panel" }, [
    h("header", {}, [
      h("button", { class: "tiny ghost", onclick: back }, "← Worlds"),
      h("span", { style: "margin-left:8px" }, details.label || details.world_id),
      details.series ? h("span", { class: "badge series", style: "margin-left:8px" }, details.series) : null,
      h("span", { class: "badge species", style: "margin-left:6px" }, details.species),
      h("span", { class: "spacer" }),
      h("button", { class: "tiny ghost", onclick: () => replay(details) }, "Replay this seed"),
    ]),
    h("div", { class: "body" }, [
      h("div", { class: "grid-3", style: "gap:10px" }, [
        stat("episodes", fmt.int(details.counts.episodes)),
        stat("step rows", fmt.int(details.counts.steps)),
        stat("updates", fmt.int(details.counts.updates)),
        stat("deaths", fmt.int(details.counts.deaths)),
        stat("snapshots", fmt.int(details.counts.snapshots)),
        stat("episode = steps", fmt.int(details.episode_length)),
      ]),
      h("div", { class: "muted mono", style: "margin-top:12px;font-size:11px" },
        `commit ${(details.commit || "—").slice(0, 10)} · torch ${details.versions?.torch} · ${details.genes.length} genes`),
      h("div", { style: "margin-top:10px" }, sessions.map((session) =>
        h("div", { class: "mono muted", style: "font-size:11px" },
          `session ${session.session}: steps ${session.from_step}–${session.to_step}, ` +
          `episodes ${session.from_episode}–${session.to_episode}, seed ${session.seed}` +
          (session.resumed_from ? ` · resumed from ${session.resumed_from}` : "")))),
    ]),
  ]);
}

function stat(name, value) {
  return h("div", { class: "panel", style: "background:#0c0e12" }, h("div", { class: "body", style: "padding:10px 12px" }, [
    h("div", { class: "muted", style: "font-size:11px" }, name),
    h("div", { class: "mono", style: "font-size:18px;margin-top:2px" }, value),
  ]));
}

// ---------------- charts ----------------

function line(name, data, color, extra = {}) {
  return {
    name,
    type: "line",
    data,
    smooth: 0.15,
    symbol: "none",
    lineStyle: { width: 1.6, color },
    itemStyle: { color },
    ...extra,
  };
}

function drawRewards(node, rewards) {
  const chart = echarts.init(node, null, { renderer: "canvas" });

  chart.setOption({
    ...chartBase(),
    xAxis: { ...chartBase().xAxis, data: rewards.episodes, name: "episode", nameLocation: "end", nameTextStyle: { color: "#5b6373" } },
    series: [
      line("shaped", rewards.shaped, CHART_COLORS.cyan, {
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(34,211,238,.22)" },
            { offset: 1, color: "rgba(34,211,238,0)" },
          ]),
        },
      }),
      line("env", rewards.env, CHART_COLORS.lime),
      line("curiosity", rewards.intrinsic, CHART_COLORS.magenta),
    ],
  });

  new ResizeObserver(() => chart.resize()).observe(node);
}

function drawLearning(node, learning) {
  const chart = echarts.init(node, null, { renderer: "canvas" });
  const base = chartBase();

  chart.setOption({
    ...base,
    grid: { ...base.grid, right: 52 },
    xAxis: { ...base.xAxis, data: learning.episodes },
    yAxis: [
      { ...base.yAxis, name: "loss", nameTextStyle: { color: "#5b6373" } },
      { ...base.yAxis, name: "td", position: "right", splitLine: { show: false } },
    ],
    series: [
      line("loss", learning.loss, CHART_COLORS.amber),
      line("|td error|", learning.td_error, CHART_COLORS.violet, { yAxisIndex: 1 }),
    ],
  });

  new ResizeObserver(() => chart.resize()).observe(node);
}

function populationChart(rewards) {
  const node = h("div", { class: "chart" });

  requestAnimationFrame(() => {
    const chart = echarts.init(node, null, { renderer: "canvas" });
    const base = chartBase();

    chart.setOption({
      ...base,
      xAxis: { ...base.xAxis, data: rewards.episodes },
      series: [
        line("agents", rewards.agents, CHART_COLORS.cyan, {
          areaStyle: { color: "rgba(34,211,238,.12)" },
        }),
        { name: "births", type: "bar", data: rewards.births, itemStyle: { color: CHART_COLORS.lime }, barMaxWidth: 6 },
        { name: "deaths", type: "bar", data: rewards.deaths, itemStyle: { color: CHART_COLORS.red }, barMaxWidth: 6 },
      ],
    });

    new ResizeObserver(() => chart.resize()).observe(node);
  });

  return node;
}

// ---------------- family tree ----------------

function drawTree(node, family) {
  if (!family.nodes.length) {
    node.replaceChildren(h("div", { class: "empty" }, "No births recorded yet"));
    return;
  }

  const byId = new Map(family.nodes.map((agent) => [agent.id, agent]));

  // One parent makes a tree, two make a graph. The tree is drawn through
  // the FIRST parent, and the second parent is shown on the card - which
  // keeps a mendel population readable instead of turning it into a mesh.
  const roots = [];
  const stratified = new Map();

  for (const agent of family.nodes) {
    const parent = agent.parents.find((id) => byId.has(id));
    const entry = { agent, children: [] };
    stratified.set(agent.id, entry);
    if (!parent) roots.push(entry);
  }

  for (const entry of stratified.values()) {
    const parent = entry.agent.parents.find((id) => stratified.has(id));
    if (parent) stratified.get(parent).children.push(entry);
  }

  const virtualRoot = { agent: null, children: roots };
  const hierarchy = d3.hierarchy(virtualRoot, (d) => d.children);

  const width = node.clientWidth || 900;
  const height = 520;

  const layout = d3.tree().size([width - 60, height - 70]);
  layout(hierarchy);

  const svg = d3.select(node).append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  const canvas = svg.append("g").attr("transform", "translate(30, 40)");

  canvas.selectAll("path.link")
    .data(hierarchy.links().filter((link) => link.source.data.agent))
    .join("path")
    .attr("class", "link")
    .attr("d", d3.linkVertical().x((d) => d.x).y((d) => d.y));

  const card = h("div", { class: "card", style: "display:none" });
  document.body.append(card);

  const nodes = canvas.selectAll("g.node")
    .data(hierarchy.descendants().filter((d) => d.data.agent))
    .join("g")
    .attr("class", (d) => `node ${d.data.agent.alive ? "alive" : "dead"}`)
    .attr("transform", (d) => `translate(${d.x},${d.y})`);

  nodes.append("circle")
    .attr("r", (d) => 5 + Math.min(6, (d.data.agent.offspring || 0) * 1.5))
    .attr("fill", (d) => (d.data.agent.alive ? CHART_COLORS.lime : "#4b5563"));

  nodes.append("text")
    .attr("y", -11)
    .attr("text-anchor", "middle")
    .attr("fill", "#5b6373")
    .style("font", "10px ui-monospace, Menlo, monospace")
    .text((d) => `#${d.data.agent.index}`);

  nodes
    .on("mousemove", (event, d) => showCard(card, event, d.data.agent))
    .on("mouseleave", () => { card.style.display = "none"; });

  // The card lives on <body>, so leaving the panel entirely must hide it.
  node.addEventListener("mouseleave", () => { card.style.display = "none"; });
}

function showCard(card, event, agent) {
  const genes = Object.entries(agent.phenotype || {}).sort(([a], [b]) => a.localeCompare(b));

  card.replaceChildren(
    h("h4", {}, `Agent #${agent.index} ${agent.alive ? "· alive" : "· died"}`),
    h("div", { class: "kv" }, [
      h("span", {}, "born"), h("span", {}, `step ${agent.birth_step}`),
      h("span", {}, "parents"), h("span", {}, agent.parents.length ? agent.parents.map((id) => id.slice(-4)).join(" + ") : "founder"),
      h("span", {}, "lifespan"), h("span", {}, agent.lifespan === null ? "—" : `${fmt.int(agent.lifespan)} ticks`),
      h("span", {}, "reward"), h("span", {}, agent.cumulative_reward === null ? "—" : fmt.number(agent.cumulative_reward, 1)),
      h("span", {}, "offspring"), h("span", {}, agent.offspring ?? "—"),
      h("span", {}, "death"), h("span", {}, agent.cause_of_death || "—"),
    ]),
    h("div", { class: "genes" }, [
      h("div", { class: "muted", style: "margin-bottom:4px" }, "phenotype"),
      h("div", { class: "kv" }, genes.flatMap(([name, value]) => [
        h("span", {}, name),
        h("span", {}, fmt.number(value, value > 100 ? 0 : 4)),
      ])),
    ]),
  );

  card.style.display = "block";
  card.style.left = `${Math.min(event.clientX + 16, window.innerWidth - 380)}px`;
  card.style.top = `${Math.min(event.clientY + 14, window.innerHeight - 320)}px`;
}
