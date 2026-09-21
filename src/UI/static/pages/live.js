// A world as video: the map, and the agents gliding across it.
//
// A run goes at full speed, where a thousand steps pass between two
// frames and there is nothing to see. While this page is open it asks the
// run to slow down to a watchable speed - renewing the request every two
// seconds - and when the page is left the requests stop and the run goes
// back to full speed by itself.
//
// Frames arrive down one open stream (no request per frame), and between
// two frames every agent is moved smoothly from where it was to where it
// is going, so the picture plays at the screen's own frame rate.

import { api, h, fmt, route, cleanup, every, button } from "../lib.js";

// empty, food, danger: the map's own colours, which mean something and so
// stay out of the orange of the panel.
const CELLS = [[14, 14, 16], [46, 160, 67], [218, 54, 51]];

const SIZE = 520;
const SPEEDS = [[5, "5/s"], [10, "10/s"], [30, "30/s"], [60, "60/s"], [0, "full speed"]];

// Remembered between visits: whoever watches at 10 a second wants 10 next
// time too.
let chosenSpeed = 30;

export function livePage(root, id) {
  const dpr = window.devicePixelRatio || 1;
  const canvas = h("canvas", { width: SIZE * dpr, height: SIZE * dpr });
  const side = h("div", { class: "side" });
  const title = h("span", {}, "connecting…");
  const status = h("span", { class: "badge" }, "waiting");
  const speeds = h("div", { class: "row", style: "gap:0" });

  let running = true;

  const ask = () => { if (running) api.watch(id, chosenSpeed).catch(() => {}); };

  const drawSpeeds = () => {
    speeds.replaceChildren(...SPEEDS.map(([speed, text]) => h("span", {
      class: `chip ${speed === chosenSpeed ? "on" : ""}`,
      style: "margin:0 4px 0 0",
      onclick: () => { chosenSpeed = speed; drawSpeeds(); ask(); },
    }, text)));
  };

  drawSpeeds();

  root.replaceChildren(h("div", { class: "page" }, h("div", { class: "panel" }, [
    h("header", {}, [
      h("a", { class: "btn small ghost", href: route.worlds(), title: "Back to worlds" }, "←"),
      title,
      status,
      h("span", { class: "spacer" }),
      h("span", { class: "note" }, "watch at"),
      speeds,
      h("a", { class: "btn small", href: route.world(id) }, "Charts"),
      button({
        label: "Stop", icon: "stop", kind: "danger", small: true,
        title: "Stop the run now; it writes a checkpoint on the way out",
        onclick: () => api.stopWorld(id).catch((error) => { status.textContent = error.message; }),
      }),
    ]),
    h("div", { class: "live-stage" }, [h("div", { class: "screen" }, canvas), side]),
  ])));

  // Keep the run slowed down while this page is open; let go on leaving.
  ask();
  every(2000, ask);
  cleanup(() => { api.watch(id, 0).catch(() => {}); });

  const player = new Player(canvas);
  cleanup(() => player.stop());

  const stream = api.stream(id);
  cleanup(() => stream.close());

  stream.onmessage = (message) => {
    const frame = JSON.parse(message.data);
    running = frame.running;

    player.push(frame);

    title.textContent = frame.label || frame.world_id;
    status.className = frame.running ? "badge live" : "badge";
    status.textContent = frame.running ? (frame.rate ? `running · ${frame.rate} steps/s` : "running · full speed") : "finished";

    side.replaceChildren(
      stat("step", fmt.int(frame.step)),
      stat("episode", fmt.int(frame.episode)),
      stat("agents", fmt.int(frame.agents)),
      stat("reward this episode", fmt.number(frame.reward, 1)),
      stat("epsilon", fmt.number(frame.epsilon, 3)),
      stat("speed", `${fmt.number(frame.steps_per_second, 0)} steps/s`),
      frame.running && !frame.rate
        ? h("div", { class: "hint" }, "Full speed: these are samples, agents jump. Pick a speed above to see every step.")
        : null,
    );
  };
}

function stat(name, value) {
  return h("div", { class: "stat" }, [h("div", { class: "name" }, name), h("div", { class: "value" }, value)]);
}

// ---------------- the player ----------------

class Player {
  constructor(canvas) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.map = document.createElement("canvas");
    this.mapKey = null;
    this.size = 64;

    this.from = new Map();
    this.to = new Map();
    this.startedAt = 0;
    this.span = 50;
    this.arrivedAt = 0;

    this.running = true;
    this.draw = this.draw.bind(this);
    requestAnimationFrame(this.draw);
  }

  stop() { this.running = false; }

  push(frame) {
    const now = performance.now();

    if (frame.grid !== this.mapKey) {
      this.paintMap(frame);
      this.mapKey = frame.grid;
    }

    // Whatever is on screen right now is where the glide to the new frame
    // starts - so a frame that comes early or late never makes anything jump.
    const current = this.positions(now);
    const next = new Map(frame.positions.map(([agentId, x, y]) => [agentId, [x, y]]));

    this.from = new Map();

    for (const [agentId, target] of next) {
      const start = current.get(agentId);

      // A newborn appears where it is born; an agent that moved more than a
      // cell between two frames (a fast run, sampled) jumps rather than
      // sliding across cells it never walked through.
      const far = !start || Math.abs(start[0] - target[0]) > 1.5 || Math.abs(start[1] - target[1]) > 1.5;
      this.from.set(agentId, far ? target : start);
    }

    this.to = next;

    if (this.arrivedAt) {
      const gap = now - this.arrivedAt;
      this.span = Math.min(600, Math.max(16, this.span * 0.7 + gap * 0.3));
    }

    this.arrivedAt = now;
    this.startedAt = now;
  }

  positions(now) {
    const t = Math.min(1, Math.max(0, (now - this.startedAt) / this.span));
    const out = new Map();

    for (const [agentId, target] of this.to) {
      const start = this.from.get(agentId) || target;
      out.set(agentId, [start[0] + (target[0] - start[0]) * t, start[1] + (target[1] - start[1]) * t]);
    }

    return out;
  }

  paintMap(frame) {
    const size = frame.size;
    const binary = atob(frame.grid);
    const image = new ImageData(size, size);

    for (let index = 0; index < binary.length; index += 1) {
      const [r, g, b] = CELLS[binary.charCodeAt(index)] || CELLS[0];
      image.data[index * 4] = r;
      image.data[index * 4 + 1] = g;
      image.data[index * 4 + 2] = b;
      image.data[index * 4 + 3] = 255;
    }

    this.size = size;
    this.map.width = size;
    this.map.height = size;
    this.map.getContext("2d").putImageData(image, 0, 0);
  }

  draw(now) {
    if (!this.running) return;

    const { context, canvas } = this;
    const scale = canvas.width / this.size;

    context.imageSmoothingEnabled = false;
    context.fillStyle = "#070708";
    context.fillRect(0, 0, canvas.width, canvas.height);

    if (this.mapKey) context.drawImage(this.map, 0, 0, canvas.width, canvas.height);

    context.fillStyle = "#ffa657";

    for (const [x, y] of this.positions(now).values()) {
      context.beginPath();
      context.arc((x + 0.5) * scale, (y + 0.5) * scale, Math.max(2, scale * 0.42), 0, Math.PI * 2);
      context.fill();
    }

    requestAnimationFrame(this.draw);
  }
}

// ---------------- a window opened before its world existed ----------------

export async function liveRunPage(root, runId) {
  const message = h("div", { class: "empty" }, "Starting the run…");
  root.replaceChildren(h("div", { class: "page" }, h("div", { class: "panel" }, message)));

  if (runId === "pending") return;

  let alive = true;
  cleanup(() => { alive = false; });

  // The window opened on the click; the run names its world a moment
  // later, in its first heartbeat. Ask until it has.
  while (alive) {
    try {
      const { world, state } = await api.runWorld(runId);

      if (world) {
        location.replace(`${location.pathname}${location.search}${route.live(world)}`);
        return;
      }

      if (state === "crashed" || state === "stopped" || state === "finished") {
        message.textContent = `The run ${state} before it showed a single frame. Its console is on the Launch page.`;
        return;
      }

      message.textContent = state === "queued" ? "Waiting in the queue…" : "Starting the run…";
    } catch (error) {
      message.textContent = error.message;
    }

    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}

