"""
Starting runs and stopping them - one at a time.

A run is a separate process of src/run.py with every prompt already
answered on the command line. The panel never imports the simulation and
never shares a python process with it: a run that dies takes nothing with
it, and the panel stays answerable while one is training.

Runs go strictly one after another. Asking for ten is ten entries in a
queue, not ten processes, which is exactly what "ten times forty thousand
steps" needs: press once, walk away. Running several at the same time is
left for when there are containers to put them in - on one laptop they
only take cores from each other.
"""

import os
import signal
import subprocess
import sys
import threading
import time

from src.utils.rng import RunRandom

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    def state(self):
        if self.process is None:
            return "stopped" if self.returncode is not None else "queued"

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
    """The queue of runs, and the only thing in the panel that starts one."""

    def __init__(self, console_dir, python=None):
        """console_dir: where each run's stdout goes - the panel's own
        folder, never logs/."""
        self.python = python or sys.executable
        self.console_dir = console_dir

        self.runs = []
        self.lock = threading.Lock()

        os.makedirs(console_dir, exist_ok=True)

        self.tick_thread = threading.Thread(target=self._loop, daemon=True)
        self.tick_thread.start()

    # -----------------------------
    # LAUNCHING
    # -----------------------------
    def submit(self, request):
        """
        request: what the launch form filled in. `repeat` asks for that
        many runs of the same shape, one after another, a different seed
        each - ten runs of one seed would be one run ten times.
        """
        repeat = max(1, int(request.get("repeat", 1)))
        created = []

        with self.lock:
            for number in range(repeat):
                identifier = f"{int(time.time() * 1000)}-{len(self.runs)}"
                single = dict(request)

                if number and single.get("seed") is not None:
                    single["seed"] = int(single["seed"]) + number

                run = Run(
                    identifier,
                    single,
                    self._command(single),
                    os.path.join(self.console_dir, f"{identifier}.log"),
                )

                self.runs.append(run)
                created.append(run)

        self._start_next()

        return [run.summary() for run in created]

    def _command(self, request):
        command = [self.python, os.path.join("src", "run.py")]

        for flag, key in (
            ("--episodes", "episodes"),
            ("--agents", "agents"),
            ("--species", "species"),
        ):
            value = request.get(key)

            if value not in (None, "", 0):
                command += [flag, str(value)]

        # Every question the runner could ask is answered here, empty ones
        # included: a flag left out makes the runner ask, and a run started
        # from the panel has nobody to reply. An empty seed becomes a real
        # one now, so the command line says which seed the run got.
        seed = request.get("seed")
        command += ["--seed", str(seed if seed not in (None, "") else RunRandom.new_seed())]
        command += ["--label", str(request.get("label") or "")]

        # Always explicit: an empty --resume is what tells the runner to
        # build a new world instead of asking which one to continue.
        command += ["--resume", str(request.get("resume") or "")]
        command += ["--pin"] if request.get("pin") else ["--no-pin"]

        return command

    def _start_next(self):
        with self.lock:
            if any(run.state() == "running" for run in self.runs):
                return

            for run in self.runs:
                if run.state() == "queued":
                    self._start(run)
                    return

    def _start(self, run):
        environment = dict(os.environ)
        environment.update({"PYTHONPATH": REPO_ROOT, "PYTHONUNBUFFERED": "1"})

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
            self._start_next()
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
        up again rather than one you lost. A run still in the queue is
        simply taken out of it.
        """
        run = self.get(identifier)

        if run is None:
            return None

        if run.state() == "queued":
            run.returncode = -15
            run.finished_at = time.time()
        elif run.state() == "running":
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
        states = [run.state() for run in self.runs]

        return {
            "cpus": os.cpu_count(),
            "running": states.count("running"),
            "queued": states.count("queued"),
            "runs": [run.summary() for run in reversed(self.runs)],
        }
