// One world: what can be done to it, and everything it did.
//
// The page is a header of actions over the run view - the same view the
// Launch page shows for the run that is going, live map included when this
// world is still running.

import { api, h, button, menu, go, route } from "../lib.js";
import { runView } from "./run.js";
import { replay, resume, archive, remove, stop, keep, rename } from "./worlds.js";

export async function worldPage(root, id) {
  const [catalog, details] = await Promise.all([api.worlds(), api.details(id)]);

  const entry = catalog.worlds.find((world) => world.id === id) || { id, seeds: [] };
  const stage = h("div", { class: "stack" });

  root.replaceChildren(h("div", { class: "page" }, [header(entry, details), stage]));

  await runView(stage, id, { live: Boolean(entry.running) });
}

function header(entry, details) {
  const world = { ...entry, sessions: details.sessions, species: details.species, label: details.label };
  const again = () => location.reload();

  // Only what is worth a button of its own stays on the row; the rest is one
  // click away in the menu, so the header cannot grow past the window.
  return h("div", { class: "page-head" }, [
    button({
      icon: "back", kind: "ghost", title: "Back to worlds",
      onclick: () => (history.length > 1 ? history.back() : go(route.worlds())),
    }),
    h("h1", { class: "ellipsis" }, details.label || details.world_id),
    h("span", { class: "badge" }, details.species),
    entry.running ? h("span", { class: "badge live" }, "running") : null,
    entry.extinct ? h("span", { class: "badge", title: "Every agent starved: nothing to continue" }, "extinct") : null,
    h("span", { class: "spacer" }),
    entry.running
      ? button({ label: "Stop", icon: "stop", kind: "danger", onclick: () => stop(world, again) })
      : null,
    entry.checkpoint && !entry.running && !entry.extinct
      ? button({ label: "Continue", icon: "resume", kind: "primary", onclick: () => resume(world, again) })
      : null,
    menu([
      entry.checkpoint && !entry.checkpoint.pinned && !entry.extinct
        ? { label: "Keep checkpoint", icon: "keep", onclick: () => keep(world, again) }
        : null,
      entry.running ? null : { label: "Rename", icon: "rename", onclick: () => rename(world, again) },
      { label: "Replay with the same seed", icon: "replay", onclick: () => replay(world) },
      { label: "Archive", icon: "archive", onclick: () => archive(world, () => go(route.worlds())) },
      { label: "Delete", icon: "delete", danger: true, onclick: () => remove(world, () => go(route.worlds())) },
    ]),
  ]);
}
