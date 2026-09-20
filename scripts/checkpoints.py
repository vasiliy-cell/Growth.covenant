"""
Look at the checkpoints on disk, and decide which ones outlive the rest.

Rolling checkpoints overwrite each other: only the newest `keep` survive,
which is what stops a month of experiments from filling a disk with 100 MB
files. A checkpoint worth going back to gets pinned, and a pinned one is
never deleted by anybody.

    PYTHONPATH=. python scripts/checkpoints.py list
    PYTHONPATH=. python scripts/checkpoints.py show 1
    PYTHONPATH=. python scripts/checkpoints.py pin 1
    PYTHONPATH=. python scripts/checkpoints.py unpin 1

A checkpoint is named by the number `list` printed next to it, by
`latest`, by its file name, or by any unique piece of one - a run id or a
step is enough. Nobody should have to retype
20260920-183709-229d1f_step000000080.pt to keep it.

Resuming one is not done here - it is the first question `python src/run.py`
asks.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import yaml

from src.persistence.checkpoint import Checkpoint
from src.persistence.checkpoint_store import CheckpointStore


def load_store():
    with open(os.path.join(REPO_ROOT, "config.yml"), "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    checkpoints = config.get("checkpoints", {})

    return CheckpointStore(
        directory=os.path.join(REPO_ROOT, checkpoints.get("dir", "checkpoints")),
        keep=int(checkpoints.get("keep", 5)),
    )


def find(store, selector):
    """
    Turns what a human typed into exactly one checkpoint.

    A number is the position `list` printed, `latest` is the newest of
    all, and anything else is matched against the file names - a whole
    name, a run id, a step, any unique piece of one. An ambiguous piece is
    an error and not a guess: these files are the only copy of a run.
    """
    found = store.list()

    if not found:
        raise SystemExit("No checkpoints yet")

    if selector == "latest":
        return found[0]

    if selector.isdigit():
        number = int(selector)

        if not 1 <= number <= len(found):
            raise SystemExit(f"There is no checkpoint {number} (see `list`)")

        return found[number - 1]

    matches = [c for c in found if selector in c["name"]]

    if not matches:
        raise SystemExit(f"Nothing matches {selector} (see `list`)")

    if len(matches) > 1:
        names = "\n  ".join(c["name"] for c in matches)
        raise SystemExit(f"{selector} matches several checkpoints:\n  {names}")

    return matches[0]


def command_list(store, _):
    found = store.list()

    if not found:
        print("No checkpoints yet")
        return

    for number, checkpoint in enumerate(found, start=1):
        print(
            f"{number:>3}. "
            f"{'[pinned] ' if checkpoint['pinned'] else '         '}"
            f"{checkpoint['name']}"
            f"  step {checkpoint['step']}"
            f"  {checkpoint['size'] / 1e6:6.1f} MB"
            f"  {checkpoint['saved_at']:%Y-%m-%d %H:%M}"
        )


def command_show(store, args):
    """The only command that opens a file - these are big."""
    checkpoint = find(store, args.name)
    record = CheckpointStore.load(checkpoint["path"])

    print(Checkpoint.describe(record))
    print(f"  file:    {checkpoint['name']}")
    print(f"  pinned:  {checkpoint['pinned']}")
    print(f"  commit:  {record.get('commit')}")
    print(f"  schema:  {record.get('schema_version')}")
    print(f"  minds:   {len(record['brains'])}")
    print(f"  streams: {len(record['rng']['streams'])}")


def command_pin(store, args):
    checkpoint = find(store, args.name)

    if checkpoint["pinned"]:
        print(f"Already pinned: {checkpoint['name']}")
        return

    print(f"Pinned, and nothing will delete it: {store.pin(checkpoint['name'])}")


def command_unpin(store, args):
    checkpoint = find(store, args.name)

    if not checkpoint["pinned"]:
        print(f"Not pinned: {checkpoint['name']}")
        return

    print(f"Back in the rolling pool: {store.unpin(checkpoint['name'])}")


COMMANDS = {
    "list": command_list,
    "show": command_show,
    "pin": command_pin,
    "unpin": command_unpin,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument(
        "name",
        nargs="?",
        help="a number from `list`, `latest`, or any unique part of a name",
    )

    args = parser.parse_args()

    if args.command in ("show", "pin", "unpin") and not args.name:
        raise SystemExit(f"{args.command} needs a checkpoint (see `list`)")

    COMMANDS[args.command](load_store(), args)


if __name__ == "__main__":
    main()
