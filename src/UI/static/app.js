// The panel itself: three views, one place that decides which is on screen.

import { api, h } from "./api.js";
import { catalog } from "./views/catalog.js";
import { world } from "./views/world.js";
import { monitor, stop as stopMonitor } from "./views/monitor.js";
import { launch, stop as stopLaunch, setPrefill } from "./views/launch.js";

const root = document.getElementById("view");
const tabs = document.getElementById("tabs");

const state = { view: "catalog", world: null };

function show(view, id = null) {
  state.view = view;
  state.world = id;

  // Only one view may hold a timer: two of them polling at once is how a
  // panel starts eating the machine it is meant to be watching.
  stopMonitor();
  stopLaunch();

  for (const tab of tabs.children) {
    tab.classList.toggle("active", tab.dataset.view === view);
  }

  render().catch((error) => {
    root.replaceChildren(h("div", { class: "panel" }, h("div", { class: "empty" }, error.message)));
  });
}

async function render() {
  if (state.view === "world" && state.world) {
    return world(root, state.world, {
      back: () => show("catalog"),
      replay: replayFrom,
    });
  }

  if (state.view === "monitor") return monitor(root);
  if (state.view === "launch") return launch(root);

  return catalog(root, { open: (id) => show("world", id), replay: replayFrom });
}

function replayFrom(source) {
  // A replay is not a continuation: it is a NEW world that starts from the
  // same seed, with every setting already filled in so only the one you
  // came to change has to be typed.
  const config = source.config || {};

  setPrefill({
    seed: (source.seeds && source.seeds[0]) ?? config.seed ?? "",
    species: source.species,
    label: source.label ? `${source.label} (replay)` : "",
    series: source.series || "",
    agents: (source.sessions && source.sessions[0]?.config?.agents?.count) || 1,
  });

  show("launch");
}

for (const tab of tabs.children) {
  tab.addEventListener("click", () => show(tab.dataset.view));
}

// The header counters, whatever view is open.
setInterval(async () => {
  try {
    const [{ runs, cpus, parallel }, { worlds }] = await Promise.all([api.runs(), api.live()]);
    const running = runs.filter((run) => run.state === "running").length;

    document.getElementById("running-pill").textContent =
      `${running} running · ${worlds.filter((w) => w.running).length} live`;
    document.getElementById("cpu-pill").textContent = `${parallel} at once · ${cpus} cores`;
  } catch { /* the header is not worth an error */ }
}, 2000);

show("catalog");
