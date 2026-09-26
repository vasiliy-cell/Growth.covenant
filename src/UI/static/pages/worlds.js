// The first page: every world in logs/, and everything you can do to one.

import { api, h, fmt, button, menu, modal, toggle, go, route, every, redraw } from "../lib.js";

export async function worldsPage(root) {
  const head = h("div", { class: "page-head" });
  const running = h("div", {});
  const table = h("div", {});

  root.replaceChildren(h("div", { class: "page" }, [head, running, table]));

  const draw = async () => {
    const { worlds } = await api.worlds();

    head.replaceChildren(...heading(worlds));
    running.replaceChildren(...runningRows(worlds, draw));

    // The table is only rebuilt when a world appears, disappears or
    // changes state - not every three seconds while somebody is reading
    // it or scrolling it sideways.
    redraw(table, signature(worlds), () => tablePanel(worlds, draw));
  };

  await draw();
  every(3000, () => draw().catch(() => {}));
}

function signature(worlds) {
  return JSON.stringify(worlds.map((world) => [
    world.id, world.label, world.episodes, world.last_step, world.deaths,
    world.running, world.extinct, world.checkpoint && world.checkpoint.step,
  ]));
}

function heading(worlds) {
  const size = worlds.reduce((sum, world) => sum + world.size, 0);

  return [
    h("h1", {}, "Worlds"),
    h("span", { class: "sub" }, `${worlds.length} worlds · ${fmt.bytes(size)}`),
    h("span", { class: "spacer" }),
    button({ label: "New run", icon: "plus", kind: "primary", onclick: () => go(route.launch()) }),
  ];
}

function tablePanel(worlds, reload) {
  if (!worlds.length) {
    return h("div", { class: "panel" }, h("div", { class: "empty" }, [
      "No worlds yet. Press ", h("b", {}, "New run"), " to make the first one.",
    ]));
  }

  return h("div", { class: "panel table-scroll" }, [
    h("table", {}, [
      h("thead", {}, h("tr", {}, [
        h("th", {}, "World"),
        h("th", { class: "num" }, "Episodes"),
        h("th", {}, "Started"),
        h("th", {}, ""),
      ])),
      h("tbody", {}, worlds.map((world) => row(world, reload))),
    ]),
  ]);
}

function runningRows(worlds, reload) {
  const running = worlds.filter((world) => world.running);

  if (!running.length) return [];

  return [h("div", { class: "panel" }, [
    h("header", {}, ["Running now", h("span", { class: "note" }, `${running.length}`)]),
    h("table", {}, h("tbody", {}, running.map((world) => h("tr", {
      class: "clickable",
      onclick: (event) => { if (!event.target.closest("button")) go(route.world(world.id)); },
    }, [
      h("td", { class: "name" }, h("div", { class: "ellipsis" }, world.label || world.world_id)),
      h("td", { class: "num" }, `step ${fmt.int(world.live && world.live.step)}`),
      h("td", { class: "num" }, `${fmt.int(world.live && world.live.agents)} agents`),
      h("td", { class: "num" }, `${fmt.number(world.live && world.live.steps_per_second, 0)} steps/s`),
      h("td", { class: "actions" }, h("div", { class: "row" }, [
        button({ icon: "watch", kind: "primary", small: true, title: "Open the world: live map and charts", onclick: () => go(route.world(world.id)) }),
        button({ icon: "stop", kind: "danger", small: true, title: "Stop this run", onclick: () => stop(world, reload) }),
      ])),
    ])))),
  ])];
}

function row(world, reload) {
  // Only what tells one world from another at a glance: what it is called,
  // how far it went, when it started. Everything else is one click away on
  // the world's own page, and every action is behind the menu.
  const canContinue = world.checkpoint && !world.running && !world.extinct;
  const canKeep = world.checkpoint && !world.checkpoint.pinned && !world.extinct;

  return h("tr", { class: "clickable", onclick: (event) => { if (!event.target.closest("button")) go(route.world(world.id)); } }, [
    h("td", { class: "name" }, [
      h("div", { class: "row", style: "gap:8px;flex-wrap:nowrap" }, [
        h("div", { class: "ellipsis" }, world.label || h("span", { class: "dim" }, "unnamed")),
        world.running ? h("span", { class: "badge live" }, "running") : null,
        world.extinct ? h("span", { class: "badge", title: "Every agent starved" }, "extinct") : null,
      ]),
      h("div", { class: "dim mono ellipsis", style: "font-size:11px;margin-top:2px" }, world.world_id),
    ]),
    h("td", { class: "num" }, fmt.int(world.episodes)),
    h("td", { class: "muted" }, fmt.ago(world.created_at)),
    // Icons, not words: a running world showed four labelled buttons here
    // and pushed its own row past the edge of the table.
    h("td", { class: "actions" }, h("div", { class: "row" }, [
      world.running
        ? button({ icon: "watch", kind: "primary", small: true, title: "Open: live map and charts", onclick: () => go(route.world(world.id)) })
        : null,
      world.running
        ? button({ icon: "stop", kind: "danger", small: true, title: "Stop this run", onclick: () => stop(world, reload) })
        : null,
      canContinue
        ? button({ icon: "resume", small: true, title: "Continue from the newest checkpoint", onclick: () => resume(world, reload) })
        : null,
      menu([
        canKeep ? { label: "Keep checkpoint", icon: "keep", onclick: () => keep(world, reload) } : null,
        world.running ? null : { label: "Rename", icon: "rename", onclick: () => rename(world, reload) },
        { label: "Replay with the same seed", icon: "replay", onclick: () => replay(world) },
        { label: "Archive", icon: "archive", onclick: () => archive(world, reload) },
        { label: "Delete", icon: "delete", danger: true, onclick: () => remove(world, reload) },
      ]),
    ])),
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
