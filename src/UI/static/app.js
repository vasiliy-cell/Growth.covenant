// The router: the address bar decides which page is on screen, so the
// browser's back and forward buttons work like on any other site.

import { api, h, leavePage } from "./lib.js";
import { worldsPage } from "./pages/worlds.js";
import { worldPage } from "./pages/world.js";
import { comparePage } from "./pages/compare.js";
import { launchPage } from "./pages/launch.js";
import { livePage, liveRunPage } from "./pages/live.js";

const root = document.getElementById("view");

const PAGES = [
  [/^#\/world\/(.+)$/, "worlds", (id) => worldPage(root, id)],
  [/^#\/compare(?:\/(metrics|charts))?$/, "compare", (step) => comparePage(root, step || "runs")],
  [/^#\/launch$/, "launch", () => launchPage(root)],
  [/^#\/live\/(.+)$/, null, (id) => livePage(root, id)],
  [/^#\/live-run\/(.+)$/, null, (id) => liveRunPage(root, id)],
  [/^(#\/?)?$/, "worlds", () => worldsPage(root)],
];

async function render() {
  leavePage();

  const hash = location.hash || "#/";

  for (const [pattern, tab, page] of PAGES) {
    const match = hash.match(pattern);
    if (!match) continue;

    for (const link of document.querySelectorAll("#tabs a")) {
      link.classList.toggle("active", link.dataset.page === tab);
    }

    try {
      // An optional part of a route that is absent comes back undefined,
      // and decodeURIComponent(undefined) is the STRING "undefined" - which
      // is how Compare once received a step called "undefined".
      await page(...match.slice(1).map((part) => (part === undefined ? undefined : decodeURIComponent(part))));
    } catch (error) {
      root.replaceChildren(h("div", { class: "page" }, h("div", { class: "panel" },
        h("div", { class: "empty" }, error.message))));
    }
    return;
  }

  location.replace("#/");
}

window.addEventListener("hashchange", render);
render();

// The queue in the title bar, whatever page is open.
async function queue() {
  try {
    const { running, queued } = await api.runs();
    const pill = document.getElementById("queue-pill");

    // Plain words, and nothing at all when nothing is happening.
    const parts = [];
    if (running) parts.push(`${running} run in progress`);
    if (queued) parts.push(`${queued} waiting`);

    pill.textContent = parts.join(" · ");
    pill.hidden = !parts.length;
    pill.classList.toggle("on", running > 0);
  } catch { /* the title bar is not worth an error */ }
}

queue();
setInterval(queue, 2000);
