"""
Starting runs, stopping them, and not letting them fight over the cpu.

A run is a separate process of src/run.py with every prompt already
answered on the command line. The panel never imports the simulation and
never shares a python process with it: a run that dies takes nothing with
it, and the panel stays answerable while ten of them are training.

Threads are the part that needs care. Torch takes the whole machine by
default, so two runs on a ten core laptop end up with twenty threads
fighting for ten cores and both go slower than either would alone. Each
child is given cpu_count // (runs it shares the machine with), decided
when it starts.
"""

import os
import signal
import subprocess
import sys
import threading
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONSOLE_DIR = os.path.join(REPO_ROOT, "logs", "_panel")


class Run:
    """One launched process, and what it was launched with."""

    def __init__(self, identifier, request, command, console_path):
        self.id = identifier
        self.request = request
        self.command = command
        self.console_path = console_path

        self.process = None
        self.started_at = None
        self.finished_at = None
        self.returncode = None
        self.threads = None

    def state(self):
        if self.process is None:
            return "queued"

        if self.returncode is None:
            return "running"

        if self.returncode == 0:
            return "finished"

        # 130 is the runner stopping on purpose; the negative codes are
        # the shell killing it before it could say so.
        return "stopped" if self.returncode in (130, -15, -2) else "crashed"

    def summary(self):
        return {
            "id": self.id,
            "state": self.state(),
            "pid": self.process.pid if self.process else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "returncode": self.returncode,
            "threads": self.threads,
            "command": self.command,
            "request": self.request,
            "console": os.path.relpath(self.console_path, REPO_ROOT),
        }

    def tail(self, lines=200):
        if not os.path.isfile(self.console_path):
            return ""

        with open(self.console_path, encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])


class Launcher:
    """
    The queue of runs, and the only thing in the panel that starts one.

    A request for ten runs is ten entries in this queue, not ten processes:
    `parallel` of them are alive at a time and the rest wait, which is what
    makes "ten times forty thousand steps" a thing you press once and walk
    away from.
    """

    def __init__(self, parallel=2, python=None):
        self.parallel = parallel
        self.python = python or sys.executable

        self.runs = []
        self.lock = threading.Lock()

        os.makedirs(CONSOLE_DIR, exist_ok=True)

        self.tick_thread = threading.Thread(target=self._loop, daemon=True)
        self.tick_thread.start()

    # -----------------------------
    # LAUNCHING
    # -----------------------------
    def submit(self, request):
        """
        request: what the launch form filled in. `repeat` asks for that
        many runs of the same shape - a different seed each, which is
        exactly what a series is.
        """
        repeat = max(1, int(request.get("repeat", 1)))
        created = []

        with self.lock:
            for number in range(repeat):
                identifier = f"{int(time.time() * 1000)}-{len(self.runs)}-{number}"
                single = dict(request)

                if repeat > 1 and single.get("seed") is not None:
                    # Ten runs of one seed are one run ten times. Only the
                    # first keeps the seed that was asked for.
                    single["seed"] = int(single["seed"]) + number if number else single["seed"]

                run = Run(
                    identifier,
                    single,
                    self._command(single),
                    os.path.join(CONSOLE_DIR, f"{identifier}.log"),
                )

                self.runs.append(run)
                created.append(run)

        self._start_what_fits()

        return [run.summary() for run in created]

    def _command(self, request):
        command = [self.python, os.path.join("src", "run.py")]

        for flag, key in (
            ("--episodes", "episodes"),
            ("--seed", "seed"),
            ("--agents", "agents"),
            ("--species", "species"),
            ("--label", "label"),
            ("--series", "series"),
            ("--live-every", "live_every"),
        ):
            value = request.get(key)

            if value not in (None, ""):
                command += [flag, str(value)]

        # Always explicit: an empty --resume is what tells the runner to
        # build a new world instead of asking which one to continue.
        command += ["--resume", str(request.get("resume") or "")]
        command += ["--pin"] if request.get("pin") else ["--no-pin"]

        for override in request.get("overrides") or []:
            if str(override).strip():
                command += ["--set", str(override).strip()]

        return command

    def _start_what_fits(self):
        with self.lock:
            running = [run for run in self.runs if run.state() == "running"]
            queued = [run for run in self.runs if run.state() == "queued"]

            # How many will be sharing the machine once the queue is going,
            # not how many happen to be up at this instant: starting two
            # runs a second apart must not give the first one all the cores
            # for the rest of its life.
            sharing = min(self.parallel, len(running) + len(queued))

            for run in queued:
                if len(running) >= self.parallel:
                    break

                self._start(run, sharing=sharing)
                running.append(run)

    def _start(self, run, sharing):
        environment = dict(os.environ)

        # One process alone gets the machine; two get half of it each.
        run.threads = max(1, (os.cpu_count() or 2) // max(1, sharing))

        environment.update({
            "PYTHONPATH": REPO_ROOT,
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": str(run.threads),
            "MKL_NUM_THREADS": str(run.threads),
        })

        console = open(run.console_path, "w", encoding="utf-8")

        run.process = subprocess.Popen(
            run.command,
            cwd=REPO_ROOT,
            env=environment,
            stdout=console,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        run.started_at = time.time()

    # -----------------------------
    # WATCHING
    # -----------------------------
    def _loop(self):
        while True:
            self._reap()
            self._start_what_fits()
            time.sleep(1.0)

    def _reap(self):
        with self.lock:
            for run in self.runs:
                if run.process is None or run.returncode is not None:
                    continue

                code = run.process.poll()

                if code is not None:
                    run.returncode = code
                    run.finished_at = time.time()

    # -----------------------------
    # STOPPING
    # -----------------------------
    def stop(self, identifier):
        """
        SIGTERM, which the runner turns into a graceful stop: it writes a
        checkpoint on the way out, so a stopped run is a run you can pick
        up again rather than one you lost.
        """
        run = self.get(identifier)

        if run is None:
            return None

        if run.state() == "queued":
            run.returncode = -15
            run.finished_at = time.time()
            return run.summary()

        if run.state() == "running":
            os.kill(run.process.pid, signal.SIGTERM)

        return run.summary()

    def get(self, identifier):
        for run in self.runs:
            if run.id == identifier:
                return run

        return None

    def clear_finished(self):
        with self.lock:
            self.runs = [run for run in self.runs if run.state() in ("queued", "running")]

    def summary(self):
        return {
            "parallel": self.parallel,
            "cpus": os.cpu_count(),
            "runs": [run.summary() for run in reversed(self.runs)],
        }
