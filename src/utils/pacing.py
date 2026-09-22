import json
import os
import time


class Pacer:
    """
    How fast the loop may go, and whether anybody is watching it.

    A run goes at full speed unless one of two things slows it down:

      - `render`, a fixed rate from the command line (--render N), for a
        run that is meant to be watched from the start,
      - a watch request: a small file the panel keeps rewriting while its
        live view of this world is open, saying how many steps a second
        the watcher wants and until when.

    The request carries a deadline because a viewer can vanish without a
    word - a closed tab, a crashed browser. A request past its deadline is
    nobody watching, and the run goes back to full speed on its own.

    The file is looked at twice a second, not every step: at full speed a
    stat per step would be the most expensive thing in the loop.
    """

    CHECK_EVERY = 0.5

    def __init__(self, render=0, watch_path=None):
        self.render = int(render or 0)
        self.watch_path = watch_path

        self.watched = 0
        self.checked_at = 0.0
        self.next_tick = time.monotonic()
        self.last_rate = 0

    @property
    def rate(self):
        """Steps per second to run at, or 0 for as fast as it can go."""
        now = time.monotonic()

        if now - self.checked_at >= self.CHECK_EVERY:
            self.checked_at = now
            self.watched = self._read_watch()

        return self.render or self.watched

    def _read_watch(self):
        if not self.watch_path:
            return 0

        try:
            with open(self.watch_path, encoding="utf-8") as handle:
                request = json.load(handle)
        except (OSError, ValueError):
            return 0

        if request.get("until", 0) < time.time():
            return 0

        return max(0, int(request.get("speed", 0)))

    def tick(self):
        """Waits out whatever is left of this step's share of a second."""
        rate = self.rate

        if not rate:
            self.last_rate = 0
            return

        # Slowing down from full speed starts the clock now, instead of
        # "catching up" on a schedule nobody was keeping.
        if rate != self.last_rate:
            self.next_tick = time.monotonic()
            self.last_rate = rate

        self.next_tick += 1.0 / rate
        delay = self.next_tick - time.monotonic()

        if delay > 0:
            time.sleep(delay)
        else:
            # Fell behind (a slow gradient step): carry on from now rather
            # than sprinting through the backlog.
            self.next_tick = time.monotonic()
