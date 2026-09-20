import os
import re
import shutil
from datetime import datetime

import torch

# <run id>_step<global step>.pt - the run that wrote it and the tick it was
# written at, both readable without opening a 100 MB file.
NAME = re.compile(r"^(?P<run_id>.+)_step(?P<step>\d+)\.pt$")


class CheckpointStore:
    """
    Where checkpoints live, how many survive and which ones are safe.

    Two pools, because a checkpoint is expensive and most of them are
    worthless an hour later:

      rolling - <directory>/*.pt. Every periodic save lands here and the
        oldest are deleted as new ones arrive, so the pool never grows past
        `keep` files however long the run is and however many runs there
        have been. A resume normally comes from here.
      pinned  - <directory>/pinned/*.pt. Nothing is ever deleted from here.
        A checkpoint is moved in by hand (scripts/checkpoints.py) or by a
        run that was started as one worth keeping.

    Writing is atomic. A checkpoint is the one file that must never be half
    written: a crash in the middle of a save would leave a file that looks
    resumable and is not, which is worse than having no checkpoint at all.
    So it goes to a temporary name, is forced to the disk, and only then
    takes its real name with os.replace - which either happens completely
    or does not happen.
    """

    def __init__(self, directory="checkpoints", keep=5):
        self.directory = directory
        self.pinned_directory = os.path.join(directory, "pinned")
        self.keep = keep

    # -----------------------------
    # WRITING
    # -----------------------------
    def save(self, record, run_id, step, pinned=False):
        """Writes one checkpoint, prunes the pool and returns its path."""
        directory = self.pinned_directory if pinned else self.directory
        os.makedirs(directory, exist_ok=True)

        path = os.path.join(directory, f"{run_id}_step{step:09d}.pt")
        self._write(record, path)

        if not pinned:
            self.prune()

        return path

    @staticmethod
    def _write(record, path):
        """torch.save through a temporary file and one atomic rename."""
        temporary = path + ".writing"

        with open(temporary, "wb") as handle:
            torch.save(record, handle)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)

    def prune(self):
        """Deletes the oldest rolling checkpoints and returns what went."""
        rolling = self.list(pinned=False)

        if self.keep <= 0 or len(rolling) <= self.keep:
            return []

        dropped = rolling[self.keep:]

        for checkpoint in dropped:
            os.remove(checkpoint["path"])

        return dropped

    # -----------------------------
    # READING
    # -----------------------------
    def list(self, pinned=None):
        """
        Newest first. pinned=None lists both pools, True or False one.

        Only the file name and its stats are read - a listing must stay
        cheap enough to print before every run, and these files are big.
        """
        pools = []

        if pinned is not True:
            pools.append((self.directory, False))
        if pinned is not False:
            pools.append((self.pinned_directory, True))

        found = []

        for directory, is_pinned in pools:
            if not os.path.isdir(directory):
                continue

            for name in os.listdir(directory):
                match = NAME.match(name)

                if match is None:
                    continue

                path = os.path.join(directory, name)

                found.append({
                    "name": name,
                    "path": path,
                    "run_id": match.group("run_id"),
                    "step": int(match.group("step")),
                    "pinned": is_pinned,
                    "size": os.path.getsize(path),
                    "saved_at": datetime.fromtimestamp(os.path.getmtime(path)),
                })

        return sorted(found, key=lambda item: item["saved_at"], reverse=True)

    def latest(self, pinned=None):
        found = self.list(pinned=pinned)

        return found[0] if found else None

    @staticmethod
    def load(path):
        """
        weights_only=False: a checkpoint is a whole run, not a tensor bag -
        genotypes, visit counts and rng states are plain python objects.
        These files are written by this project and read back by it.
        """
        return torch.load(path, weights_only=False)

    # -----------------------------
    # PINNING
    # -----------------------------
    def pin(self, name):
        """Moves a rolling checkpoint where nothing will ever delete it."""
        source = os.path.join(self.directory, name)

        if not os.path.isfile(source):
            raise FileNotFoundError(f"No rolling checkpoint named {name}")

        os.makedirs(self.pinned_directory, exist_ok=True)
        target = os.path.join(self.pinned_directory, name)

        shutil.move(source, target)

        return target

    def unpin(self, name):
        """Back into the rolling pool - and into reach of the next prune."""
        source = os.path.join(self.pinned_directory, name)

        if not os.path.isfile(source):
            raise FileNotFoundError(f"No pinned checkpoint named {name}")

        os.makedirs(self.directory, exist_ok=True)
        target = os.path.join(self.directory, name)

        shutil.move(source, target)

        return target

    def __repr__(self):
        return (
            f"CheckpointStore(dir={self.directory}, keep={self.keep}, "
            f"rolling={len(self.list(pinned=False))}, "
            f"pinned={len(self.list(pinned=True))})"
        )
