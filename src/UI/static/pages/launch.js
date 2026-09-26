// Starting runs, and watching the one that is going.
//
// One page, scrolled: the form and the queue at the top, and under them the
// run itself - its live map, its stats and every chart of it. Starting a run
// does not send you anywhere; the page simply grows.

import { api, h, fmt, button, segmented, toggle, every, redraw, setText, leavePage } from "../lib.js";
import { runView } from "./run.js";

// Which world the lower half of the page is about. It outlives one render of
// the page, because picking another run rebuilds the page around it.
let watching = null;

export async function launchPage(root) {
  const { config, cpus } = await api.config();

  const prefill = JSON.parse(sessionStorage.getItem("prefill") || "null");
  sessionStorage.removeItem("prefill");

  const queue = h("div", {});
  const stage = h("div", { class: "stack" });

  const rebuild = () => {
    // A different run means different everything below: the live stream, the
    // charts, the tree. Building the page again is how they all let go at
    // once instead of half of them staying behind.
    leavePage();
    launchPage(root).catch(() => {});
  };

  root.replaceChildren(h("div", { class: "page" }, [
    h("div", { class: "page-head" }, [
      h("h1", {}, prefill ? "Replay" : "Launch"),
      h("span", { class: "sub" }, `episode = ${config.run?.episode_length ?? 20} steps · ${cpus} cores`),
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "panel" }, h("div", { class: "body" }, form(config, prefill || {}))),
      queue,
    ]),
    stage,
  ]));

  let shown = null;

  const refresh = async () => {
    try {
      const state = await api.runs();

      // The queue is only rebuilt when a run changes state. Rebuilding it
      // every second and a half threw away the console somebody was reading -
      // and their place in it.
      const built = redraw(
        queue,
        JSON.stringify(state.runs.map((run) => [run.id, run.state, run.world])),
        () => queuePanel(state, rebuild),
      );

      if (!built) refreshConsoles();

      // Nothing picked yet: follow the run that is going. The launcher runs
      // one at a time, so there is never a question which one that is.
      const going = state.runs.find((run) => run.state === "running" && run.world);
      const target = watching || (going && going.world);

      if (target && target !== shown) {
        shown = target;
        watching = target;
        await runView(stage, target, { live: Boolean(going && going.world === target) });
      } else if (!target && !shown) {
        stage.replaceChildren(h("div", { class: "panel" }, h("div", { class: "empty" }, [
          "Nothing is running. ", h("b", {}, "Start"), " a run and it appears here - map, charts and family tree.",
        ])));
      } else if (going && going.world !== shown && !newRunOffered(stage)) {
        offerNewRun(stage, going.world, rebuild);
      }
    } catch { /* next time */ }
  };

  await refresh();
  every(1500, refresh);
}

function newRunOffered(stage) {
  return Boolean(stage.querySelector(".new-run"));
}

function offerNewRun(stage, world, rebuild) {
  stage.prepend(h("div", { class: "panel new-run" }, h("div", { class: "body row" }, [
    h("span", { class: "badge live" }, "a newer run is going"),
    h("span", { class: "muted" }, "the charts below are the previous one"),
    h("span", { class: "spacer" }),
    button({
      label: "Show the new run", kind: "primary", small: true,
      onclick: () => { watching = world; rebuild(); },
    }),
  ])));
}

// ---------------- the form ----------------

function field(label, control, hint) {
  return h("div", { class: "field" }, [
    h("label", { class: "field-label" }, label),
    control,
    hint ? h("div", { class: "hint" }, hint) : null,
  ]);
}

function form(config, prefill) {
  const values = {
    species: prefill.species || config.genome?.type || "clons",
    pin: false,
  };

  const episodes = h("input", { type: "number", min: "1", value: prefill.episodes || 1000 });
  const agents = h("input", { type: "number", min: "1", value: prefill.agents || config.agents?.count || 1 });
  const seed = h("input", { type: "number", placeholder: "random", value: prefill.seed ?? "" });
  const runs = h("input", { type: "number", min: "1", value: 1 });
  const label = h("input", { placeholder: "what this experiment is", value: prefill.label || "" });

  const species = segmented(
    [["clons", "clons"], ["non_linear", "non linear"], ["mendel", "mendel"]],
    values.species,
    (key) => { values.species = key; },
  );

  const dice = button({
    icon: "dice",
    title: "Random seed",
    onclick: () => { seed.value = Math.floor(Math.random() * 1e9); },
  });

  const message = h("span", { class: "mono accent", style: "font-size:12px" });

  const start = button({
    label: "Start",
    icon: "resume",
    kind: "primary big",
    onclick: async () => {
      start.disabled = true;
      message.textContent = "starting…";

      try {
        const count = Math.max(1, Number(runs.value) || 1);
        await api.launch({
          episodes: Number(episodes.value),
          agents: Number(agents.value),
          species: values.species,
          seed: seed.value === "" ? null : Number(seed.value),
          label: label.value,
          repeat: count,
          pin: values.pin,
        });

        // Whatever was being watched, the new run is what this page is about
        // now: it appears below by itself.
        watching = null;

        message.textContent = count > 1
          ? `a series of ${count} runs is queued - they go one after another`
          : "started - it appears below in a moment";
      } catch (error) {
        message.textContent = error.message;
      } finally {
        start.disabled = false;
      }
    },
  });

  return h("div", {}, [
    field("Species", species),
    h("div", { class: "fields" }, [
      field("Episodes", episodes),
      field("Agents", agents),
      field("Series", runs, "how many runs: same settings, a new seed each, one after another"),
    ]),
    field("Seed", h("div", { class: "input-with-button" }, [seed, dice]), "empty = a random one; in a series each next run takes the next seed"),
    field("Label", label),
    h("div", { class: "option" }, [
      toggle(false, (on) => { values.pin = on; }),
      h("div", {}, [
        h("div", { class: "title" }, "Keep the final checkpoint"),
        h("div", { class: "hint" }, "it goes to checkpoints/pinned and is never rotated away"),
      ]),
    ]),
    h("div", { class: "row", style: "margin-top:14px;gap:14px" }, [start, message]),
  ]);
}

// ---------------- the queue ----------------

const BADGES = { running: "badge live", queued: "badge warn", crashed: "badge bad" };

// Which consoles are open, and the element showing each one - so their text
// can be refreshed in place instead of being rebuilt under the reader.
const openConsoles = new Map();

function refreshConsoles() {
  for (const [id, node] of openConsoles) {
    if (!node.isConnected) {
      openConsoles.delete(id);
      continue;
    }

    api.console(id).then(({ console: text }) => setText(node, text || "(nothing yet)"));
  }
}

function queuePanel(state, rebuild) {
  return h("div", { class: "panel" }, [
    h("header", {}, [
      "Runs",
      h("span", { class: "note" }, `${state.running} running · ${state.queued} waiting`),
      h("span", { class: "spacer" }),
      state.runs.some((run) => !["running", "queued"].includes(run.state))
        ? button({ label: "Clear finished", kind: "ghost", small: true, onclick: () => api.clear() })
        : null,
    ]),
    state.runs.length
      ? h("div", { class: "scroller" }, state.runs.map((run) => runRow(run, rebuild)))
      : h("div", { class: "empty" }, "Nothing queued yet. Runs you start appear here."),
  ]);
}

function runRow(run, rebuild) {
  const request = run.request || {};
  const console = h("pre", { class: "console", hidden: !openConsoles.has(run.id) });

  if (openConsoles.has(run.id)) {
    openConsoles.set(run.id, console);
    api.console(run.id).then(({ console: text }) => setText(console, text || "(nothing yet)"));
  }

  const what = request.resume
    ? `continue ${request.label || ""} · +${fmt.int(request.episodes)} episodes`
    : `${request.label || "unnamed"} · ${request.species} · ${fmt.int(request.episodes)} episodes · seed ${request.seed ?? "random"}`;

  return h("div", { style: "border-bottom:1px solid var(--border)" }, [
    h("div", { class: "row", style: "padding:9px 12px;flex-wrap:nowrap" }, [
      h("span", { class: BADGES[run.state] || "badge" }, run.state),
      h("span", { class: "mono", style: "font-size:11px;overflow:hidden;text-overflow:ellipsis" }, what),
      h("span", { class: "spacer" }),
      run.world
        ? button({
          icon: "watch", small: true, kind: run.world === watching ? "primary" : "",
          title: "Show this run below",
          onclick: () => {
            if (run.world === watching) return;
            watching = run.world;
            rebuild();
          },
        })
        : null,
      button({
        icon: "console", small: true, title: "Console",
        onclick: async () => {
          console.hidden = !console.hidden;

          if (console.hidden) {
            openConsoles.delete(run.id);
          } else {
            openConsoles.set(run.id, console);
            setText(console, (await api.console(run.id)).console || "(nothing yet)");
          }
        },
      }),
      ["running", "queued"].includes(run.state)
        ? button({ icon: "stop", small: true, kind: "danger", title: "Stop (a checkpoint is written on the way out)", onclick: () => api.stop(run.id) })
        : null,
    ]),
    console,
  ]);
}
