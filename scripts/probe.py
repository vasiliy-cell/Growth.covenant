"""
Run the probe worlds of a finished run: every agent of every snapshot it
left, alone and frozen in a fresh copy of its world (src/probe/runner.py).

    PYTHONPATH=. python scripts/probe.py list
    PYTHONPATH=. python scripts/probe.py run 1          # number from `list`,
    PYTHONPATH=. python scripts/probe.py run latest     # `latest`, or part
    PYTHONPATH=. python scripts/probe.py run 20261107   # of a folder name

Probe worlds already on disk are skipped, so an interrupted batch is
carried on by running the same command again.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import yaml

from src.persistence.log_reader import RunLogReader
from src.probe.runner import run_probes, snapshots_of


def logs_directory():
    with open(os.path.join(REPO_ROOT, "config.yml"), "r", encoding="utf-8") as f:
        config = yaml.safe_load(f).get("logging", {})

    return os.path.join(REPO_ROOT, config.get("dir", "logs"))


def find(worlds, selector):
    """A number from `list`, `latest`, or any unique part of a folder name."""
    if not worlds:
        raise SystemExit("No logs yet")

    if selector == "latest":
        return worlds[0]

    if selector.isdigit() and len(selector) < 6:
        number = int(selector)

        if not 1 <= number <= len(worlds):
            raise SystemExit(f"There is no world {number} (see `list`)")

        return worlds[number - 1]

    matches = [
        world for world in worlds if selector in os.path.basename(world.path)
    ]

    if not matches:
        raise SystemExit(f"Nothing matches {selector} (see `list`)")

    if len(matches) > 1:
        names = "\n  ".join(os.path.basename(world.path) for world in matches)
        raise SystemExit(f"{selector} matches several worlds:\n  {names}")

    return matches[0]


def command_list(args):
    worlds = RunLogReader.find(logs_directory())

    if not worlds:
        print("No logs yet")
        return

    for number, world in enumerate(worlds, start=1):
        print(
            f"{number:>3}. {os.path.basename(world.path)}"
            f"  {len(snapshots_of(world.path))} probe snapshot(s)"
        )


def command_run(args):
    world = find(RunLogReader.find(logs_directory()), args.name)

    print(f"Probing {world.path}")
    written = run_probes(world.path)
    print(f"{len(written)} probe world(s) written")


def main():
    parser = argparse.ArgumentParser(description="Run the probe worlds.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="worlds and their probe snapshots")

    run = commands.add_parser("run", help="probe every snapshot of a world")
    run.add_argument("name", help="number from `list`, `latest`, or part of a name")

    args = parser.parse_args()

    {"list": command_list, "run": command_run}[args.command](args)


if __name__ == "__main__":
    main()
