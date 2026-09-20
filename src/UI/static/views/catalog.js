// Every world on disk, and what can be done to one.

import { api, h, fmt, modal } from "../api.js";

export async function catalog(root, { open, replay }) {
  const { worlds } = await api.worlds();

  if (!worlds.length) {
    root.replaceChildren(
      h("div", { class: "panel" }, h("div", { class: "empty" }, [
        "No worlds yet. ",
        h("b", {}, "Launch"), " one and it will appear here.",
      ])),
    );
    return;
  }

  const series = new Set(worlds.map((world) => world.series).filter(Boolean));

  const table = h("table", {}, [
    h("thead", {}, h("tr", {}, [
      h("th", {}, ""),
      h("th", {}, "World"),
      h("th", {}, "Series"),
      h("th", {}, "Species"),
      h("th", { class: "num" }, "Episodes"),
      h("th", { class: "num" }, "Steps"),
      h("th", { class: "num" }, "Deaths"),
      h("th", { class: "num" }, "Size"),
      h("th", { class: "num" }, "Seed"),
      h("th", {}, "Created"),
      h("th", {}, ""),
    ])),
    h("tbody", {}, worlds.map((world) => row(world, { open, replay, reload: () => catalog(root, { open, replay }) }))),
  ]);

  root.replaceChildren(
    h("div", { class: "stack" }, [
      h("div", { class: "panel flush" }, [
        h("header", {}, [
          "Worlds",
          h("span", { class: "spacer" }),
          h("span", { class: "muted mono" },
            `${worlds.length} worlds · ${series.size} series · ${fmt.bytes(worlds.reduce((sum, w) => sum + w.size, 0))}`),
        ]),
        h("div", {}, table),
      ]),
    ]),
  );
}

function row(world, { open, replay, reload }) {
  const name = world.label || world.world_id;

  return h("tr", { onclick: (event) => { if (!event.target.closest("button")) open(world.id); } }, [
    h("td", {}, world.running ? h("span", { class: "live-dot", title: "running" }) : ""),
    h("td", {}, [
      h("div", {}, name),
      h("div", { class: "dim mono", style: "font-size:11px" }, world.world_id),
    ]),
    h("td", {}, world.series ? h("span", { class: "badge series" }, world.series) : h("span", { class: "dim" }, "—")),
    h("td", {}, h("span", { class: "badge species" }, world.species || "—")),
    h("td", { class: "num" }, fmt.int(world.episodes)),
    h("td", { class: "num" }, fmt.int(world.last_step)),
    h("td", { class: "num" }, fmt.int(world.deaths)),
    h("td", { class: "num" }, fmt.bytes(world.size)),
    h("td", { class: "num dim" }, world.seeds[0] ?? "—"),
    h("td", { class: "muted" }, fmt.ago(world.created_at)),
    h("td", {}, h("div", { class: "row", style: "gap:6px;justify-content:flex-end" }, [
      h("button", { class: "tiny ghost", onclick: () => open(world.id) }, "Open"),
      h("button", { class: "tiny ghost", title: "start a new run from this seed", onclick: () => replay(world) }, "Replay"),
      h("button", { class: "tiny ghost", onclick: () => archive(world, reload) }, "Archive"),
      h("button", { class: "tiny danger", onclick: () => remove(world, reload) }, "Delete"),
    ])),
  ]);
}

function archive(world, reload) {
  const note = h("input", { placeholder: "what this experiment was", value: world.label || "" });
  const alsoDelete = h("input", { type: "checkbox" });

  modal({
    title: `Archive ${world.label || world.world_id}`,
    confirm: "Archive",
    body: h("div", {}, [
      h("div", { class: "field" }, [h("label", {}, "Note (required)"), note]),
      h("label", { class: "check" }, [alsoDelete, h("span", {}, "delete the logs after packing them")]),
      h("p", { class: "muted", style: "margin:12px 0 0" },
        "The note is written next to the archive as well as inside it, so it can be read without unpacking."),
    ]),
    onConfirm: async () => {
      if (!note.value.trim()) throw new Error("An archive needs a note");
      await api.archive(world.id, note.value.trim(), alsoDelete.checked);
      reload();
    },
  });
}

function remove(world, reload) {
  const confirmation = h("input", { placeholder: world.world_id });

  modal({
    title: "Delete this world",
    confirm: "Delete forever",
    danger: true,
    body: h("div", {}, [
      h("div", { class: "warn" }, [
        h("b", {}, "Nothing is kept. "),
        "Every step, every life and every snapshot of this world goes. ",
        "If you might ever want it back, archive it instead.",
      ]),
      h("div", { class: "field" }, [
        h("label", {}, `Type the world id to confirm: ${world.world_id}`),
        confirmation,
      ]),
    ]),
    onConfirm: async () => {
      if (confirmation.value.trim() !== world.world_id) throw new Error("That is not the world id");
      await api.remove(world.id);
      reload();
    },
  });
}
