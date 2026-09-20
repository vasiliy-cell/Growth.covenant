"""
Look at the logs, and pack the ones whose experiment is over.

Nothing in this project ever deletes a log on its own. A run keeps writing
into its world's folder and leaves it there - the only way a log goes away
is a human deciding the experiment is finished, and this is that human's
tool. Archiving takes a NOTE, because a 300 MB tarball called
20260920-193227-7d4167 tells you nothing in March.

    PYTHONPATH=. python scripts/logs.py list
    PYTHONPATH=. python scripts/logs.py show 1
    PYTHONPATH=. python scripts/logs.py archive 1 --note "mendel, leak 0.5"
    PYTHONPATH=. python scripts/logs.py archive 1 --note "..." --delete
    PYTHONPATH=. python scripts/logs.py archives
    PYTHONPATH=. python scripts/logs.py restore 1
"""

import argparse
import json
import os
import shutil
import sys
import tarfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import yaml

from src.persistence.log_reader import RunLogReader


def load_config():
    with open(os.path.join(REPO_ROOT, "config.yml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("logging", {})


def directories():
    config = load_config()

    return (
        os.path.join(REPO_ROOT, config.get("dir", "logs")),
        os.path.join(REPO_ROOT, config.get("archive_dir", "archives")),
    )


def folder_size(path):
    total = 0

    for root, _, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))

    return total


def find(worlds, selector):
    """A number from `list`, or any unique part of a folder name."""
    if not worlds:
        raise SystemExit("No logs yet")

    if selector.isdigit():
        number = int(selector)

        if not 1 <= number <= len(worlds):
            raise SystemExit(f"There is no log {number} (see `list`)")

        return worlds[number - 1]

    matches = [world for world in worlds if selector in os.path.basename(world)]

    if not matches:
        raise SystemExit(f"Nothing matches {selector} (see `list`)")

    if len(matches) > 1:
        names = "\n  ".join(os.path.basename(world) for world in matches)
        raise SystemExit(f"{selector} matches several logs:\n  {names}")

    return matches[0]


# -----------------------------
# LIVE LOGS
# -----------------------------
def command_list(args):
    logs, _ = directories()
    worlds = RunLogReader.find(logs)

    if not worlds:
        print("No logs yet")
        return

    for number, world in enumerate(worlds, start=1):
        print(
            f"{number:>3}. {os.path.basename(world.path)}"
            f"  {folder_size(world.path) / 1e6:7.1f} MB"
            f"  {len(world.sessions)} session(s)"
            f"  {world.episode_population().num_rows} episodes"
        )


def command_show(args):
    logs, _ = directories()
    world = find(RunLogReader.find(logs), args.name)

    print(world.describe())
    print(f"  path:     {world.path}")
    print(f"  label:    {world.label}")
    print(f"  species:  {world.header.get('species')}")
    print(f"  genes:    {len(world.genes)}")
    print(f"  versions: {world.header.get('versions')}")
    print(f"  size:     {folder_size(world.path) / 1e6:.1f} MB")

    for session in world.sessions:
        print(
            f"  session {session['session']}: "
            f"steps {session['from_step']}-{session['to_step']}, "
            f"episodes {session['from_episode']}-{session['to_episode']}, "
            f"seed {session['seed']}"
            + (
                f", resumed from {session['resumed_from']}"
                if session.get("resumed_from") else ""
            )
        )


# -----------------------------
# ARCHIVING
# -----------------------------
def command_archive(args):
    """
    Packs one world into archive_dir, with the note beside it.

    The note is not decoration: it is the only thing that will tell you in
    March what this run was for, and it sits OUTSIDE the tarball as well as
    inside it, so it can be read - and grepped - without unpacking 300 MB.
    """
    logs, archives = directories()
    world = find(RunLogReader.find(logs), args.name)

    name = os.path.basename(world.path)
    os.makedirs(archives, exist_ok=True)

    archive_path = os.path.join(archives, f"{name}.tar.gz")

    if os.path.exists(archive_path):
        raise SystemExit(f"Already archived: {archive_path}")

    note = {
        "note": args.note,
        "world_id": world.world_id,
        "label": world.label,
        "species": world.header.get("species"),
        "sessions": len(world.sessions),
        "episodes": world.episode_population().num_rows,
        "steps": world.table("steps").num_rows,
        "deaths": world.deaths().num_rows,
        "size_bytes": folder_size(world.path),
        "archived_at": time.time(),
        "source": world.path,
    }

    note_path = os.path.join(archives, f"{name}.note.json")

    with open(note_path, "w", encoding="utf-8") as handle:
        json.dump(note, handle, indent=2)

    temporary = archive_path + ".writing"

    with tarfile.open(temporary, "w:gz") as tar:
        tar.add(world.path, arcname=name)
        tar.add(note_path, arcname=os.path.join(name, "NOTE.json"))

    os.replace(temporary, archive_path)

    packed = os.path.getsize(archive_path)
    print(
        f"Archived {name}: {note['size_bytes'] / 1e6:.1f} MB -> "
        f"{packed / 1e6:.1f} MB\n  {archive_path}\n  note: {args.note}"
    )

    if args.delete:
        # Read the tarball back before deleting the only other copy.
        with tarfile.open(archive_path) as tar:
            members = tar.getnames()

        if not members:
            raise SystemExit("The archive came back empty - keeping the logs")

        shutil.rmtree(world.path)
        print(f"Deleted {world.path} ({len(members)} files are in the archive)")


def command_archives(args):
    _, archives = directories()

    if not os.path.isdir(archives):
        print("Nothing archived yet")
        return

    names = sorted(name for name in os.listdir(archives) if name.endswith(".tar.gz"))

    if not names:
        print("Nothing archived yet")
        return

    for number, name in enumerate(names, start=1):
        path = os.path.join(archives, name)
        note_path = path[: -len(".tar.gz")] + ".note.json"

        note = {}
        if os.path.isfile(note_path):
            with open(note_path, encoding="utf-8") as handle:
                note = json.load(handle)

        print(
            f"{number:>3}. {name}  {os.path.getsize(path) / 1e6:7.1f} MB"
            f"  {note.get('episodes', '?')} episodes"
            f"  \"{note.get('note', '')}\""
        )


def command_restore(args):
    _, archives = directories()
    logs, _ = directories()

    names = sorted(
        os.path.join(archives, name)
        for name in os.listdir(archives)
        if name.endswith(".tar.gz")
    ) if os.path.isdir(archives) else []

    if not names:
        raise SystemExit("Nothing archived yet")

    archive_path = find(names, args.name)

    with tarfile.open(archive_path) as tar:
        tar.extractall(logs)

    print(f"Unpacked into {logs}")


COMMANDS = {
    "list": command_list,
    "show": command_show,
    "archive": command_archive,
    "archives": command_archives,
    "restore": command_restore,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("name", nargs="?", help="a number from `list`, or part of a name")
    parser.add_argument("--note", default="", help="what this experiment was")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="remove the logs after packing them (checked first)",
    )

    args = parser.parse_args()

    if args.command in ("show", "archive", "restore") and not args.name:
        raise SystemExit(f"{args.command} needs a log (see `list`)")

    if args.command == "archive" and not args.note:
        raise SystemExit(
            "archive needs --note: an unnamed tarball is a tarball you will "
            "never open again"
        )

    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
