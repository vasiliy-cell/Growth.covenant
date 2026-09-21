// Starting runs: one, or several one after another with a new seed each.

import { api, h, fmt, button, segmented, toggle, go, route, every } from "../lib.js";

export async function launchPage(root) {
  const { config, cpus } = await api.config();

  const prefill = JSON.parse(sessionStorage.getItem("prefill") || "null");
  sessionStorage.removeItem("prefill");

  const queue = h("div", {});

  root.replaceChildren(h("div", { class: "page" }, [
    h("div", { class: "page-head" }, [
      h("h1", {}, prefill ? "Replay" : "New run"),
      h("span", { class: "sub" }, `episode = ${config.run?.episode_length ?? 20} steps · ${cpus} cores`),
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "panel" }, h("div", { class: "body", style: "padding:18px" }, form(config, prefill || {}))),
      queue,
    ]),
  ]));

  const refresh = async () => {
    try { queue.replaceChildren(await queuePanel()); } catch { /* next time */ }
  };

  await refresh();
  every(1500, refresh);
}

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

  const message = h("span", { class: "mono", style: "font-size:12px;color:var(--accent-soft)" });

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

        message.textContent = count > 1
          ? `a series of ${count} runs is queued - they go one after another`
          : "started - press Watch in the queue to see it";
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
    h("div", { class: "row", style: "margin-top:18px;gap:14px" }, [start, message]),
  ]);
}

// ---------------- the queue ----------------

const BADGES = { running: "badge live", queued: "badge warn", crashed: "badge bad" };

// The queue is redrawn every second and a half; a console somebody opened
// must stay open through that instead of snapping shut under them.
const openConsoles = new Set();

async function queuePanel() {
  const state = await api.runs();

  return h("div", { class: "panel" }, [
    h("header", {}, [
      "Queue",
      h("span", { class: "note" }, `${state.running} running · ${state.queued} waiting`),
      h("span", { class: "spacer" }),
      state.runs.some((run) => !["running", "queued"].includes(run.state))
        ? button({ label: "Clear finished", kind: "ghost", small: true, onclick: () => api.clear() })
        : null,
    ]),
    state.runs.length
      ? h("div", {}, state.runs.map(runRow))
      : h("div", { class: "empty" }, "Nothing queued. Runs you start appear here."),
  ]);
}

function runRow(run) {
  const request = run.request || {};
  const console = h("pre", { class: "console", hidden: !openConsoles.has(run.id) });

  if (openConsoles.has(run.id)) {
    api.console(run.id).then(({ console: text }) => { console.textContent = text || "(nothing yet)"; });
  }

  const what = request.resume
    ? `continue ${request.label || ""} · +${fmt.int(request.episodes)} episodes`
    : `${request.label || "unnamed"} · ${request.species} · ${fmt.int(request.episodes)} episodes · seed ${request.seed ?? "random"}`;

  return h("div", { style: "border-bottom:1px solid var(--border)" }, [
    h("div", { class: "row", style: "padding:11px 14px;flex-wrap:nowrap" }, [
      h("span", { class: BADGES[run.state] || "badge" }, run.state),
      h("span", { class: "mono", style: "font-size:11px;overflow:hidden;text-overflow:ellipsis" }, what),
      h("span", { class: "spacer" }),
      run.state === "running"
        ? button({ label: "Watch", icon: "watch", kind: "primary", small: true, onclick: () => go(route.liveRun(run.id)) })
        : null,
      button({
        icon: "console", small: true, title: "Console",
        onclick: async () => {
          console.hidden = !console.hidden;

          if (console.hidden) {
            openConsoles.delete(run.id);
          } else {
            openConsoles.add(run.id);
            console.textContent = (await api.console(run.id)).console || "(nothing yet)";
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
