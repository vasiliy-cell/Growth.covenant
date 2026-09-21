// One world: what it earned, what it learned, who descended from whom.

import {
  api, h, fmt, button, go, route, chartBase, chartIn, line, COLORS, cleanup,
} from "../lib.js";
import { replay, resume, archive, remove } from "./worlds.js";

// All charts of a world move together: pick a range of episodes on one
// and every other one shows the same range.
const GROUP = "world-charts";

export async function worldPage(root, id) {
  const [catalog, details, rewards, learning, family] = await Promise.all([
    api.worlds(), api.details(id), api.rewards(id), api.learning(id), api.family(id),
  ]);

  const entry = catalog.worlds.find((world) => world.id === id) || { id, seeds: [] };
  const episodes = rewards.episodes.length;

  const rewardNode = h("div", { class: "chart tall" });
  const learningNode = h("div", { class: "chart" });
  const populationNode = h("div", { class: "chart" });
  const treeNode = h("div", { class: "tree" });

  root.replaceChildren(h("div", { class: "page" }, [
    header(entry, details),
    stats(details, family),
    h("div", { class: "panel" }, [
      h("header", {}, [
        "Reward per episode",
        h("span", { class: "note" }, "env · curiosity · what the networks learned from"),
        h("span", { class: "spacer" }),
        rangeButtons(episodes),
      ]),
      h("div", { class: "body" }, rewardNode),
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "panel" }, [
        h("header", {}, ["Learning", h("span", { class: "note" }, "mean per episode")]),
        h("div", { class: "body" }, learningNode),
      ]),
      h("div", { class: "panel" }, [
        h("header", {}, ["Population", h("span", { class: "note" }, "agents · births · deaths")]),
        h("div", { class: "body" }, populationNode),
      ]),
    ]),
    h("div", { class: "panel" }, [
      h("header", {}, [
        "Family tree",
        h("span", { class: "note" }, `${family.nodes.length} agents · ${family.nodes.filter((n) => n.alive).length} alive · hover a node`),
      ]),
      h("div", { class: "body" }, treeNode),
    ]),
  ]));

  drawRewards(rewardNode, rewards);
  drawLearning(learningNode, learning);
  drawPopulation(populationNode, rewards);
  echarts.connect(GROUP);
  drawTree(treeNode, family);
}

function header(entry, details) {
  const world = { ...entry, sessions: details.sessions, species: details.species, label: details.label };

  return h("div", { class: "page-head" }, [
    button({ icon: "back", kind: "ghost", title: "Back to worlds", onclick: () => history.length > 1 ? history.back() : go(route.worlds()) }),
    h("h1", {}, details.label || details.world_id),
    h("span", { class: "badge" }, details.species),
    entry.running ? h("span", { class: "badge live" }, [h("span", { class: "live-dot" }), "running"]) : null,
    h("span", { class: "spacer" }),
    entry.running
      ? button({ label: "Watch", icon: "watch", kind: "primary", onclick: () => go(route.live(entry.id)) })
      : null,
    entry.checkpoint && !entry.running
      ? button({ label: "Continue", icon: "resume", kind: "primary", onclick: () => resume(world, () => location.reload()) })
      : null,
    button({ label: "Replay", icon: "replay", onclick: () => replay(world) }),
    button({ icon: "archive", title: "Archive", onclick: () => archive(world, () => go(route.worlds())) }),
    button({ icon: "delete", kind: "danger", title: "Delete", onclick: () => remove(world, () => go(route.worlds())) }),
  ]);
}

function stats(details, family) {
  const sessions = details.sessions || [];

  return h("div", { class: "panel" }, h("div", { class: "body" }, [
    h("div", { class: "stats" }, [
      stat("episodes", fmt.int(details.counts.episodes)),
      stat("steps", fmt.int(sessions.length ? sessions[sessions.length - 1].to_step : 0)),
      stat("agents ever", fmt.int(family.nodes.length)),
      stat("deaths", fmt.int(details.counts.deaths)),
      stat("updates", fmt.int(details.counts.updates)),
      stat("seed", sessions[0]?.seed ?? "—"),
    ]),
    h("div", { class: "mono dim", style: "font-size:11px;margin-top:12px;line-height:1.7" }, [
      `${details.world_id} · commit ${(details.commit || "—").slice(0, 10)} · episode = ${details.episode_length} steps`,
      ...sessions.map((session) => h("div", {},
        `session ${session.session}: steps ${session.from_step ?? "—"}–${session.to_step ?? "—"}, ` +
        `episodes ${session.from_episode ?? "—"}–${session.to_episode ?? "—"}` +
        (session.resumed_from ? ` · continued from ${session.resumed_from}` : ""))),
    ]),
  ]));
}

function stat(name, value) {
  return h("div", { class: "stat" }, [h("div", { class: "name" }, name), h("div", { class: "value" }, value)]);
}

// ---------------- episode range ----------------

let rewardChart = null;

function rangeButtons(episodes) {
  // How many of the last episodes the charts are drawn over. The slider
  // under the reward chart sets any range; these are the usual ones.
  const choices = [["all", "All"], [50, "Last 50"], [200, "Last 200"], [1000, "Last 1000"]]
    .filter(([size]) => size === "all" || size < episodes);

  const box = h("div", { class: "row", style: "gap:4px" });

  const pick = (size) => {
    for (const child of box.children) child.classList.toggle("on", child.dataset.size === String(size));

    if (!rewardChart) return;

    if (size === "all") {
      rewardChart.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
    } else {
      rewardChart.dispatchAction({ type: "dataZoom", startValue: Math.max(0, episodes - size), endValue: episodes - 1 });
    }
  };

  for (const [size, text] of choices) {
    box.append(h("button", { class: "chip", "data-size": size, style: "margin:0", onclick: () => pick(size) }, text));
  }

  box.firstChild?.classList.add("on");
  return box;
}

function zoomed(base) {
  return {
    ...base,
    grid: { ...base.grid, bottom: 70 },
    dataZoom: [
      { type: "inside" },
      {
        type: "slider",
        height: 22,
        bottom: 14,
        borderColor: "#26262b",
        backgroundColor: "#0c0c0e",
        fillerColor: "rgba(240,136,62,.14)",
        dataBackground: { lineStyle: { color: "#3a3a42" }, areaStyle: { color: "#1b1b1f" } },
        selectedDataBackground: { lineStyle: { color: "#f0883e" }, areaStyle: { color: "rgba(240,136,62,.2)" } },
        handleStyle: { color: "#f0883e", borderColor: "#db6d28" },
        moveHandleStyle: { color: "#35353c" },
        textStyle: { color: "#9d9da8" },
      },
    ],
  };
}

// ---------------- charts ----------------

function drawRewards(node, rewards) {
  const chart = chartIn(node);
  chart.group = GROUP;
  rewardChart = chart;
  cleanup(() => { rewardChart = null; });

  const base = zoomed(chartBase());

  chart.setOption({
    ...base,
    xAxis: { ...base.xAxis, data: rewards.episodes, name: "episode", nameTextStyle: { color: "#62626c" } },
    series: [
      line("shaped", rewards.shaped, COLORS.orange, {
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(240,136,62,.25)" },
            { offset: 1, color: "rgba(240,136,62,0)" },
          ]),
        },
      }),
      line("env", rewards.env, COLORS.blue),
      line("curiosity", rewards.intrinsic, COLORS.rose),
    ],
  });
}

function drawLearning(node, learning) {
  const chart = chartIn(node);
  chart.group = GROUP;

  const base = chartBase();

  chart.setOption({
    ...base,
    dataZoom: [{ type: "inside" }],
    grid: { ...base.grid, right: 56 },
    xAxis: { ...base.xAxis, data: learning.episodes },
    yAxis: [
      { ...base.yAxis, name: "loss", nameTextStyle: { color: "#62626c" } },
      { ...base.yAxis, name: "|td|", position: "right", splitLine: { show: false }, nameTextStyle: { color: "#62626c" } },
    ],
    series: [
      line("loss", learning.loss, COLORS.orange),
      line("|td error|", learning.td_error, COLORS.gold, { yAxisIndex: 1 }),
    ],
  });
}

function drawPopulation(node, rewards) {
  const chart = chartIn(node);
  chart.group = GROUP;

  const base = chartBase();

  chart.setOption({
    ...base,
    dataZoom: [{ type: "inside" }],
    xAxis: { ...base.xAxis, data: rewards.episodes },
    series: [
      line("agents", rewards.agents, COLORS.orange, { areaStyle: { color: "rgba(240,136,62,.12)" } }),
      { name: "births", type: "bar", data: rewards.births, itemStyle: { color: COLORS.green }, barMaxWidth: 6 },
      { name: "deaths", type: "bar", data: rewards.deaths, itemStyle: { color: COLORS.red }, barMaxWidth: 6 },
    ],
  });
}

// ---------------- family tree ----------------

function drawTree(node, family) {
  if (!family.nodes.length) {
    node.replaceChildren(h("div", { class: "empty" }, "No births recorded in this world."));
    return;
  }

  const byId = new Map(family.nodes.map((agent) => [agent.id, agent]));

  // One parent makes a tree, two make a graph. The tree is drawn through
  // the FIRST parent and the second one is named on the card - which keeps
  // a sexual population readable instead of turning it into a mesh.
  const entries = new Map();
  const roots = [];

  for (const agent of family.nodes) {
    entries.set(agent.id, { agent, children: [] });
  }

  for (const entry of entries.values()) {
    const parent = entry.agent.parents.find((parentId) => byId.has(parentId));
    if (parent) entries.get(parent).children.push(entry);
    else roots.push(entry);
  }

  const hierarchy = d3.hierarchy({ agent: null, children: roots }, (d) => d.children);

  const width = node.clientWidth || 1000;
  const height = 520;
  d3.tree().size([width - 60, height - 70])(hierarchy);

  const svg = d3.select(node).append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  const canvas = svg.append("g").attr("transform", "translate(30, 36)");

  canvas.selectAll("path.link")
    .data(hierarchy.links().filter((link) => link.source.data.agent))
    .join("path")
    .attr("class", "link")
    .attr("d", d3.linkVertical().x((d) => d.x).y((d) => d.y));

  const card = h("div", { class: "card", style: "display:none" });
  document.body.append(card);
  cleanup(() => card.remove());

  const nodes = canvas.selectAll("g.node")
    .data(hierarchy.descendants().filter((d) => d.data.agent))
    .join("g")
    .attr("class", (d) => `node ${d.data.agent.alive ? "alive" : "dead"}`)
    .attr("transform", (d) => `translate(${d.x},${d.y})`);

  nodes.append("circle")
    .attr("r", (d) => 5 + Math.min(6, (d.data.agent.offspring || 0) * 1.5))
    .attr("fill", (d) => (d.data.agent.alive ? COLORS.orange : "#4a4a53"));

  nodes.append("text")
    .attr("y", -11)
    .attr("text-anchor", "middle")
    .attr("fill", "#62626c")
    .style("font", "10px ui-monospace, Menlo, monospace")
    .text((d) => `#${d.data.agent.index}`);

  nodes
    .on("mousemove", (event, d) => showCard(card, event, d.data.agent))
    .on("mouseleave", () => { card.style.display = "none"; });

  node.addEventListener("mouseleave", () => { card.style.display = "none"; });
}

function showCard(card, event, agent) {
  const phenotype = Object.entries(agent.phenotype || {}).sort(([a], [b]) => a.localeCompare(b));

  card.replaceChildren(
    h("h4", {}, `Agent #${agent.index} · ${agent.alive ? "alive" : "died"}`),
    h("div", { class: "kv" }, [
      h("span", {}, "born"), h("span", {}, `step ${fmt.int(agent.birth_step)}`),
      h("span", {}, "parents"), h("span", {}, agent.parents.length ? agent.parents.map((p) => `#${p.split("-").pop().replace(/^0+/, "") || 0}`).join(" + ") : "founder"),
      h("span", {}, "lifespan"), h("span", {}, agent.lifespan === null ? "—" : `${fmt.int(agent.lifespan)} ticks`),
      h("span", {}, "reward"), h("span", {}, agent.cumulative_reward === null ? "—" : fmt.number(agent.cumulative_reward, 1)),
      h("span", {}, "offspring"), h("span", {}, agent.offspring ?? "—"),
      h("span", {}, "death"), h("span", {}, agent.cause_of_death || "—"),
    ]),
    h("div", { class: "genes" }, [
      h("div", { class: "muted", style: "margin-bottom:4px" }, "phenotype"),
      h("div", { class: "kv" }, phenotype.flatMap(([name, value]) => [
        h("span", {}, name),
        h("span", {}, fmt.number(value, Math.abs(value) >= 100 ? 0 : 4)),
      ])),
      genotypeLines(agent.genotype),
    ]),
  );

  card.style.display = "block";
  card.style.left = `${Math.min(event.clientX + 16, window.innerWidth - 390)}px`;
  card.style.top = `${Math.min(event.clientY + 14, window.innerHeight - 360)}px`;
}

function genotypeLines(genotype) {
  // A mendel genotype is two alleles per gene - worth seeing, because it
  // is what the phenotype above was read out of.
  if (!genotype || typeof genotype !== "object") return null;

  const entries = Object.entries(genotype).filter(([, value]) => Array.isArray(value));
  if (!entries.length) return null;

  return h("div", { style: "margin-top:8px" }, [
    h("div", { class: "muted", style: "margin-bottom:4px" }, "genotype (alleles)"),
    h("div", { class: "kv" }, entries.sort(([a], [b]) => a.localeCompare(b)).flatMap(([name, pair]) => [
      h("span", {}, name),
      h("span", {}, pair.map(([value, allele]) => `${fmt.number(value, Math.abs(value) >= 100 ? 0 : 3)}${allele}`).join("  ")),
    ])),
  ]);
}
