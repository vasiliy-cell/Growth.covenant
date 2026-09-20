// Starting runs: one, or ten of them with one press.

import { api, h, fmt } from "../api.js";

let timer = null;
let prefill = null;

export function setPrefill(values) { prefill = values; }

export async function launch(root) {
  stop();

  const { config, cpus } = await api.config();
  const values = { ...defaults(config), ...(prefill || {}) };
  prefill = null;

  const form = buildForm(values, config);
  const queue = h("div", {});

  root.replaceChildren(h("div", { class: "grid-2" }, [
    h("div", { class: "panel" }, [
      h("header", {}, ["New run", h("span", { class: "spacer" }), h("span", { class: "muted mono" }, `${cpus} cores`)]),
      h("div", { class: "body" }, form.node),
    ]),
    h("div", { class: "stack" }, [queue]),
  ]));

  const refresh = async () => {
    try { queue.replaceChildren(await runsPanel()); }
    catch { /* the panel survives a hiccup */ }
  };

  await refresh();
  timer = setInterval(refresh, 1500);
}

export function stop() {
  if (timer) clearInterval(timer);
  timer = null;
}

function defaults(config) {
  return {
    episodes: 1000,
    agents: config.agents?.count ?? 1,
    species: config.genome?.type ?? "clons",
    seed: "",
    label: "",
    series: "",
    live_every: config.logging?.live_every_steps ?? 20,
    repeat: 1,
    pin: false,
    overrides: "",
  };
}

function field(label, input) {
  return h("div", { class: "field" }, [h("label", {}, label), input]);
}

function buildForm(values, config) {
  const episodes = h("input", { type: "number", min: "1", value: values.episodes });
  const agents = h("input", { type: "number", min: "1", value: values.agents });
  const species = h("select", {}, ["clons", "non_linear", "mendel"].map((name) =>
    h("option", { value: name, selected: name === values.species }, name)));
  const seed = h("input", { placeholder: "empty = random", value: values.seed ?? "" });
  const label = h("input", { placeholder: "what this experiment is", value: values.label ?? "" });
  const series = h("input", { placeholder: "group of runs (optional)", value: values.series ?? "" });
  const liveEvery = h("input", { type: "number", min: "0", value: values.live_every });
  const repeat = h("input", { type: "number", min: "1", value: values.repeat });
  const pin = h("input", { type: "checkbox", checked: values.pin });
  const overrides = h("textarea", {
    rows: "4",
    placeholder: "life.childhood_steps=2000\nenergy.energy_leak=0.2",
  }, values.overrides || "");

  const message = h("div", { class: "muted mono", style: "font-size:11px;min-height:16px" });

  const submit = h("button", { class: "accent", onclick: async () => {
    submit.disabled = true;
    message.textContent = "starting…";

    try {
      const body = {
        episodes: Number(episodes.value),
        agents: Number(agents.value),
        species: species.value,
        seed: seed.value === "" ? null : Number(seed.value),
        label: label.value,
        series: series.value,
        live_every: Number(liveEvery.value),
        repeat: Number(repeat.value),
        pin: pin.checked,
        overrides: overrides.value.split("\n").map((line) => line.trim()).filter(Boolean),
      };

      const { launched } = await api.launch(body);
      message.textContent = `queued ${launched.length} run${launched.length > 1 ? "s" : ""}`;
    } catch (error) {
      message.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  } }, "Start");

  const node = h("div", {}, [
    h("div", { class: "fields" }, [
      field("Episodes", episodes),
      field(`Agents (episode = ${config.run?.episode_length ?? 20} steps)`, agents),
      field("Species", species),
      field("Seed", seed),
      field("Live snapshot every N steps", liveEvery),
      field("Repeat (new seed each)", repeat),
    ]),
    field("Label", label),
    field("Series", series),
    field("Config overrides, one per line", overrides),
    h("label", { class: "check", style: "margin-bottom:12px" }, [pin, h("span", {}, "keep the final checkpoint forever")]),
    h("div", { class: "row" }, [submit, message]),
  ]);

  return { node };
}

async function runsPanel() {
  const state = await api.runs();
  const parallel = h("input", { type: "number", min: "1", value: state.parallel, style: "width:64px", onchange: (event) => api.parallel(Number(event.target.value)) });

  return h("div", { class: "panel flush" }, [
    h("header", {}, [
      "Queue",
      h("span", { class: "spacer" }),
      h("span", { class: "muted", style: "margin-right:8px" }, "at once"),
      parallel,
      h("button", { class: "tiny ghost", style: "margin-left:8px", onclick: () => api.clear() }, "Clear finished"),
    ]),
    state.runs.length
      ? h("div", {}, state.runs.map(runRow))
      : h("div", { class: "empty" }, "Nothing queued"),
  ]);
}

function runRow(run) {
  const request = run.request || {};
  const console = h("pre", { class: "console", hidden: true });

  const toggle = async () => {
    console.hidden = !console.hidden;
    if (!console.hidden) console.textContent = (await api.console(run.id)).console || "(nothing yet)";
  };

  return h("div", { style: "border-bottom:1px solid var(--border)" }, [
    h("div", { class: "row", style: "padding:10px 12px;gap:10px" }, [
      h("span", { class: `badge ${run.state === "running" ? "live" : run.state === "queued" ? "queued" : run.state === "crashed" ? "crashed" : ""}` }, run.state),
      h("span", { class: "mono", style: "font-size:11px" },
        `${request.label || "unnamed"} · ${request.species} · ${fmt.int(request.episodes)} ep · seed ${request.seed ?? "random"}`),
      h("span", { class: "spacer", style: "margin-left:auto" }),
      run.threads ? h("span", { class: "muted mono", style: "font-size:11px" }, `${run.threads} threads`) : null,
      h("button", { class: "tiny ghost", onclick: toggle }, "Console"),
      ["running", "queued"].includes(run.state)
        ? h("button", { class: "tiny danger", onclick: () => api.stop(run.id) }, "Stop")
        : null,
    ]),
    console,
  ]);
}
