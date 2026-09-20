// What is happening right now, one tile per world that still has a pulse.

import { api, h, fmt } from "../api.js";

const CELL_COLORS = [
  [13, 15, 19],     // empty
  [42, 213, 88],    // food
  [212, 43, 63],    // danger
];

let timer = null;
let focused = null;

export async function monitor(root) {
  stop();

  const tiles = h("div", { class: "tiles" });
  const big = h("div", {});

  root.replaceChildren(h("div", { class: "stack" }, [big, h("div", { class: "panel flush" }, [
    h("header", {}, [
      "Live",
      h("span", { class: "spacer" }),
      h("span", { class: "muted mono", id: "live-count" }, ""),
    ]),
    h("div", { class: "body" }, tiles),
  ])]));

  const refresh = async () => {
    let worlds = [];

    try { worlds = (await api.live()).worlds; }
    catch { return; }

    document.getElementById("live-count").textContent =
      `${worlds.filter((w) => w.running).length} running · ${worlds.length} with a heartbeat`;

    if (!worlds.length) {
      tiles.replaceChildren(h("div", { class: "empty" }, "Nothing is running. Start a run from Launch."));
      big.replaceChildren();
      return;
    }

    tiles.replaceChildren(...worlds.map((live) => tile(live, () => { focused = live.id; refresh(); })));

    const chosen = worlds.find((live) => live.id === focused);
    big.replaceChildren(chosen ? bigView(chosen, () => { focused = null; refresh(); }) : "");
  };

  await refresh();
  timer = setInterval(refresh, 1000);
}

export function stop() {
  if (timer) clearInterval(timer);
  timer = null;
}

function tile(live, onOpen) {
  const canvas = h("canvas", { width: 256, height: 256 });

  requestAnimationFrame(() => paint(canvas, live));

  return h("div", { class: "panel tile", onclick: onOpen }, [
    h("header", {}, [
      live.running ? h("span", { class: "live-dot" }) : h("span", { class: "badge crashed", style: "margin-right:6px" }, "idle"),
      h("span", { style: "overflow:hidden;text-overflow:ellipsis" }, live.label || live.world_id),
      h("span", { class: "spacer" }),
      h("span", { class: "muted mono", style: "font-size:11px" }, `${fmt.int(live.step)}`),
    ]),
    canvas,
    h("div", { class: "stats" }, [
      h("span", {}, ["pop ", h("b", {}, live.agents)]),
      h("span", {}, ["rw ", h("b", {}, fmt.number(live.reward, 0))]),
      h("span", {}, ["ε ", h("b", {}, fmt.number(live.epsilon, 3))]),
      h("span", { class: "spacer", style: "margin-left:auto" }, `${fmt.number(live.steps_per_second, 0)}/s`),
    ]),
  ]);
}

function bigView(live, onClose) {
  const canvas = h("canvas", { width: 640, height: 640, style: "width:100%;max-width:640px;margin:0 auto" });

  requestAnimationFrame(() => paint(canvas, live, true));

  return h("div", { class: "panel" }, [
    h("header", {}, [
      live.running ? h("span", { class: "live-dot" }) : null,
      live.label || live.world_id,
      h("span", { class: "badge", style: "margin-left:8px" }, `episode ${live.episode}`),
      h("span", { class: "spacer" }),
      h("span", { class: "muted mono" }, `${fmt.int(live.step)} steps · ${fmt.number(live.steps_per_second, 0)}/s · pid ${live.pid}`),
      h("button", { class: "tiny ghost", style: "margin-left:10px", onclick: onClose }, "Close"),
    ]),
    h("div", { class: "body", style: "display:flex;justify-content:center" }, canvas),
  ]);
}

function paint(canvas, live, large = false) {
  const context = canvas.getContext("2d");
  const size = live.size;
  const cells = decode(live.grid);
  const scale = canvas.width / size;

  const image = context.createImageData(size, size);

  for (let index = 0; index < cells.length; index += 1) {
    const [r, g, b] = CELL_COLORS[cells[index]] || CELL_COLORS[0];
    image.data[index * 4] = r;
    image.data[index * 4 + 1] = g;
    image.data[index * 4 + 2] = b;
    image.data[index * 4 + 3] = 255;
  }

  // Draw the map at its own resolution, then blow it up without smoothing:
  // a cell is a cell, not a blur.
  const buffer = document.createElement("canvas");
  buffer.width = size;
  buffer.height = size;
  buffer.getContext("2d").putImageData(image, 0, 0);

  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(buffer, 0, 0, canvas.width, canvas.height);

  for (const [, x, y] of live.positions) {
    context.fillStyle = "#22d3ee";
    context.shadowColor = "rgba(34,211,238,.9)";
    context.shadowBlur = large ? 10 : 5;
    context.beginPath();
    context.arc((x + 0.5) * scale, (y + 0.5) * scale, Math.max(1.6, scale * 0.42), 0, Math.PI * 2);
    context.fill();
  }

  context.shadowBlur = 0;
}

function decode(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return bytes;
}
