"""
Look at the checkpoints on disk, and decide which ones outlive the rest.

Rolling checkpoints overwrite each other: only the newest `keep` survive,
which is what stops a month of experiments from filling a disk with 100 MB
files. A checkpoint worth going back to gets pinned, and a pinned one is
never deleted by anybody.

    PYTHONPATH=. python scripts/checkpoints.py list
    PYTHONPATH=. python scripts/checkpoints.py show <name>
    PYTHONPATH=. python scripts/checkpoints.py pin <name>
    PYTHONPATH=. python scripts/checkpoints.py unpin <name>

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


def command_list(store, _):
    found = store.list()

    if not found:
        print("No checkpoints yet")
        return

    for checkpoint in found:
        print(
            f"{'[pinned] ' if checkpoint['pinned'] else '         '}"
            f"{checkpoint['name']}"
            f"  step {checkpoint['step']}"
            f"  {checkpoint['size'] / 1e6:6.1f} MB"
            f"  {checkpoint['saved_at']:%Y-%m-%d %H:%M}"
        )


def command_show(store, args):
    """The only command that opens a file - these are big."""
    for checkpoint in store.list():
        if checkpoint["name"] == args.name:
            record = CheckpointStore.load(checkpoint["path"])

            print(Checkpoint.describe(record))
            print(f"  commit:  {record.get('commit')}")
            print(f"  schema:  {record.get('schema_version')}")
            print(f"  minds:   {len(record['brains'])}")
            print(f"  streams: {len(record['rng']['streams'])}")
            return

    raise SystemExit(f"No checkpoint named {args.name}")


def command_pin(store, args):
    print(f"Pinned: {store.pin(args.name)}")


def command_unpin(store, args):
    print(f"Back in the rolling pool: {store.unpin(args.name)}")


COMMANDS = {
    "list": command_list,
    "show": command_show,
    "pin": command_pin,
    "unpin": command_unpin,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("name", nargs="?", help="checkpoint file name")

    args = parser.parse_args()

    if args.command in ("show", "pin", "unpin") and not args.name:
        raise SystemExit(f"{args.command} needs a checkpoint name")

    COMMANDS[args.command](load_store(), args)


if __name__ == "__main__":
    main()
