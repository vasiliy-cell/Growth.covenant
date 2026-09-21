// The first page: every world in logs/, and everything you can do to one.

import { api, h, fmt, button, modal, toggle, go, route, every } from "../lib.js";

export async function worldsPage(root) {
  const holder = h("div", { class: "page" });
  root.replaceChildren(holder);

  const draw = async () => {
    const { worlds } = await api.worlds();
    holder.replaceChildren(...content(worlds, draw));
  };

  await draw();

  // Running worlds change under your eyes; the list follows them.
  every(3000, () => draw().catch(() => {}));
}

function content(worlds, reload) {
  const running = worlds.filter((world) => world.running);
  const size = worlds.reduce((sum, world) => sum + world.size, 0);

  const head = h("div", { class: "page-head" }, [
    h("h1", {}, "Worlds"),
    h("span", { class: "sub" }, `${worlds.length} worlds · ${fmt.bytes(size)}`),
    h("span", { class: "spacer" }),
    button({ label: "New run", icon: "plus", kind: "primary", onclick: () => go(route.launch()) }),
  ]);

  if (!worlds.length) {
    return [head, h("div", { class: "panel" }, h("div", { class: "empty" }, [
      "No worlds yet. Press ", h("b", {}, "New run"), " to make the first one.",
    ]))];
  }

  return [
    head,
    running.length ? runningPanel(running, reload) : null,
    h("div", { class: "panel" }, [
      h("table", {}, [
        h("thead", {}, h("tr", {}, [
          h("th", {}, "World"),
          h("th", {}, "Species"),
          h("th", { class: "num" }, "Episodes"),
          h("th", { class: "num" }, "Steps"),
          h("th", { class: "num" }, "Deaths"),
          h("th", { class: "num" }, "Seed"),
          h("th", {}, "Checkpoint"),
          h("th", {}, "Created"),
          h("th", {}, ""),
        ])),
        h("tbody", {}, worlds.map((world) => row(world, reload))),
      ]),
    ]),
  ].filter(Boolean);
}

function runningPanel(running, reload) {
  return h("div", { class: "panel" }, [
    h("header", {}, ["Running now", h("span", { class: "note" }, `${running.length}`)]),
    h("table", {}, h("tbody", {}, running.map((world) => h("tr", {}, [
      h("td", {}, world.label || world.world_id),
      h("td", { class: "num" }, `step ${fmt.int(world.live?.step)}`),
      h("td", { class: "num" }, `${fmt.int(world.live?.agents)} agents`),
      h("td", { class: "num" }, `${fmt.number(world.live?.steps_per_second, 0)} steps/s`),
      h("td", { class: "actions" }, h("div", { class: "row" }, [
        button({ label: "Watch", icon: "watch", kind: "primary", small: true, onclick: () => go(route.live(world.id)) }),
        button({ label: "Stop", icon: "stop", kind: "danger", small: true, onclick: () => stop(world, reload) }),
      ])),
    ])))),
  ]);
}

function row(world, reload) {
  // An extinct world has nobody to continue and nothing worth keeping.
  const canContinue = world.checkpoint && !world.running && !world.extinct;
  const canKeep = world.checkpoint && !world.checkpoint.pinned && !world.extinct;

  return h("tr", { class: "clickable", onclick: (event) => { if (!event.target.closest("button")) go(route.world(world.id)); } }, [
    h("td", {}, [
      h("div", {}, [
        world.label || h("span", { class: "dim" }, "unnamed"),
        world.running ? h("span", { class: "badge live", style: "margin-left:8px" }, "running") : null,
        world.extinct ? h("span", { class: "badge", style: "margin-left:8px", title: "Every agent starved: nothing to continue" }, "extinct") : null,
      ]),
      h("div", { class: "dim mono", style: "font-size:11px;margin-top:2px" }, world.world_id),
    ]),
    h("td", {}, h("span", { class: "badge" }, world.species || "—")),
    h("td", { class: "num" }, fmt.int(world.episodes)),
    h("td", { class: "num" }, fmt.int(world.last_step)),
    h("td", { class: "num" }, fmt.int(world.deaths)),
    h("td", { class: "num dim" }, world.seeds[0] ?? "—"),
    h("td", {}, checkpointCell(world)),
    h("td", { class: "muted" }, fmt.ago(world.created_at)),
    h("td", { class: "actions" }, h("div", { class: "row" }, [
      world.running
        ? button({ label: "Watch", icon: "watch", kind: "primary", small: true, onclick: () => go(route.live(world.id)) })
        : null,
      world.running
        ? button({ label: "Stop", icon: "stop", kind: "danger", small: true, onclick: () => stop(world, reload) })
        : null,
      canContinue
        ? button({ label: "Continue", icon: "resume", small: true, onclick: () => resume(world, reload) })
        : null,
      canKeep
        ? button({ icon: "keep", small: true, title: "Keep: this world's checkpoint is never rotated away", onclick: () => keep(world, reload) })
        : null,
      world.running
        ? null
        : button({ icon: "rename", small: true, title: "Rename", onclick: () => rename(world, reload) }),
      button({ icon: "replay", small: true, title: "Replay: a new world from the same seed", onclick: () => replay(world) }),
      button({ icon: "archive", small: true, title: "Archive", onclick: () => archive(world, reload) }),
      button({ icon: "delete", small: true, kind: "danger", title: "Delete", onclick: () => remove(world, reload) }),
    ])),
  ]);
}

function checkpointCell(world) {
  if (!world.checkpoint) {
    return h("span", {
      class: "dim",
      title: "No checkpoint left: only the newest checkpoint of the last 5 runs is kept. Press Keep on a world to protect its checkpoint.",
    }, "none");
  }

  return h("span", { class: "mono muted", style: "font-size:11px" }, [
    `step ${fmt.int(world.checkpoint.step)}`,
    world.checkpoint.pinned ? h("span", { class: "badge", style: "margin-left:6px" }, "kept") : null,
  ]);
}

// ---------------- actions ----------------
// Shared with the world page, which offers the same buttons.

export function replay(world) {
  // A replay is not a continuation: it is a NEW world from the same seed,
  // with the launch form filled in so only what you came to change needs
  // touching.
  sessionStorage.setItem("prefill", JSON.stringify({
    seed: world.seeds?.[0] ?? world.sessions?.[0]?.seed ?? "",
    species: world.species,
    label: world.label ? `${world.label} (replay)` : "",
    agents: world.agents ?? world.sessions?.[0]?.config?.agents?.count,
  }));

  go(route.launch());
}

export function resume(world, after = () => {}) {
  const episodes = h("input", { type: "number", min: "1", value: 500 });

  modal({
    title: `Continue ${world.label || world.world_id}`,
    confirm: "Continue",
    body: h("div", {}, [
      h("p", { class: "muted", style: "margin:0 0 16px" }, [
        "Picks the world up at its newest checkpoint, ",
        h("span", { class: "accent mono" }, `step ${fmt.int(world.checkpoint.step)}`),
        " - same seed, same population, same minds. The log goes on in the same folder.",
      ]),
      h("div", { class: "field", style: "margin:0" }, [h("label", { class: "field-label" }, "How many more episodes"), episodes]),
    ]),
    onConfirm: async () => {
      await api.resume(world.id, { episodes: Number(episodes.value) });
      after();
    },
  });
}

export function archive(world, after = () => {}) {
  const note = h("input", { placeholder: "what this experiment was", value: world.label || "" });
  let alsoDelete = false;

  modal({
    title: `Archive ${world.label || world.world_id}`,
    confirm: "Archive",
    body: h("div", {}, [
      h("div", { class: "field" }, [h("label", { class: "field-label" }, "Note (required)"), note]),
      h("div", { class: "option" }, [
        toggle(false, (on) => { alsoDelete = on; }),
        h("div", {}, [
          h("div", { class: "title" }, "Delete the logs after packing"),
          h("div", { class: "hint" }, "the archive is read back first; the note stays next to it"),
        ]),
      ]),
    ]),
    onConfirm: async () => {
      if (!note.value.trim()) throw new Error("An archive needs a note");
      await api.archive(world.id, note.value.trim(), alsoDelete);
      after();
    },
  });
}

export function stop(world, after = () => {}) {
  modal({
    title: `Stop ${world.label || world.world_id}?`,
    confirm: "Stop",
    danger: true,
    body: h("p", { class: "muted", style: "margin:0" },
      "The run stops now and writes a checkpoint on the way out, so the world can be continued later."),
    onConfirm: async () => {
      await api.stopWorld(world.id);
      after();
    },
  });
}

export async function keep(world, after = () => {}) {
  // Pinning moves the world's newest checkpoint where nothing rotates it
  // away - no question needed, it can be undone by moving the file back.
  await api.keep(world.id);
  after();
}

export function rename(world, after = () => {}) {
  const name = h("input", { value: world.label || "", placeholder: "a name for this world" });

  modal({
    title: "Rename world",
    confirm: "Save",
    body: h("div", { class: "field", style: "margin:0" }, [h("label", { class: "field-label" }, world.world_id), name]),
    onConfirm: async () => {
      await api.rename(world.id, name.value);
      after();
    },
  });

  setTimeout(() => name.focus(), 0);
}

export function remove(world, after = () => {}) {
  modal({
    title: `Delete ${world.label || world.world_id}?`,
    confirm: "Delete forever",
    danger: true,
    body: h("div", { class: "warn-box", style: "margin:0" }, [
      h("b", {}, "Nothing is kept. "),
      "Every step, every life and every snapshot of this world goes. If you might want it back, archive it instead.",
    ]),
    onConfirm: async () => {
      await api.remove(world.id);
      after();
    },
  });
}
