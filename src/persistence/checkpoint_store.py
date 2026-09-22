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

    TWO FOLDERS, and which folder a file is in IS whether it is pinned:

        checkpoints/rolling/   every periodic save lands here, and only
                               the newest checkpoint of each of the `keep`
                               most recent runs survives - however long a
                               run is and however many there have been,
        checkpoints/pinned/    nothing here is ever deleted by anything.

    That is the whole of the mechanism, and it is a mechanism on purpose:
    pinning is moving a file, so it works from the terminal, from a file
    manager, from a script, from anywhere. scripts/checkpoints.py is a
    convenience, not the authority.

    The two folders do not compete. A prune only ever looks at rolling/, so
    pinning four checkpoints does not cost the rolling pool a single one of
    its `keep` runs.

    Writing is atomic. A checkpoint is the one file that must never be half
    written: a crash in the middle of a save would leave a file that looks
    resumable and is not, which is worse than having no checkpoint at all.
    So it goes to a temporary name, is forced to the disk, and only then
    takes its real name with os.replace - which either happens completely
    or does not happen.
    """

    def __init__(self, directory="checkpoints", keep=5):
        self.directory = directory
        self.rolling_directory = os.path.join(directory, "rolling")
        self.pinned_directory = os.path.join(directory, "pinned")
        self.keep = keep

    def directory_for(self, pinned):
        return self.pinned_directory if pinned else self.rolling_directory

    def prepare(self):
        """
        Makes both folders, empty or not.

        A folder you cannot see is a folder you will not use: the point of
        the split is that you can open checkpoints/ and drag a file from
        one side to the other.
        """
        for directory in (self.rolling_directory, self.pinned_directory):
            os.makedirs(directory, exist_ok=True)

    # -----------------------------
    # WRITING
    # -----------------------------
    def save(self, record, run_id, step, pinned=False):
        """Writes one checkpoint, prunes the pool and returns its path."""
        self.prepare()

        directory = self.directory_for(pinned)
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
        """
        Keeps the newest checkpoint of each of the `keep` most recent runs,
        deletes everything else in rolling/, and returns what went.

        Counted by RUN, not by file. One long run saves a checkpoint every
        few hundred steps, and counted file by file those periodic saves
        pushed every other run's last checkpoint out of the pool - leaving
        one world that could be continued instead of five. A run only needs
        its newest checkpoint to be picked up again, and since every write
        is atomic the newest one is always whole.
        """
        if self.keep <= 0:
            return []

        runs = []
        dropped = []

        # Newest first, so the first file seen of a run is its newest one.
        for checkpoint in self.list(pinned=False):
            run = checkpoint["run_id"]

            if run in runs or len(runs) >= self.keep:
                dropped.append(checkpoint)
            else:
                runs.append(run)

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
            pools.append((self.rolling_directory, False))

            # Loose files straight in checkpoints/ are from before the
            # folder split. They are read and pruned like any other
            # rolling checkpoint, so nobody loses a run to a refactor.
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
        """
        Moves a rolling checkpoint where nothing will ever delete it.

        Exactly the same thing as dragging the file into pinned/ - this is
        here to save typing, not because moving it by hand is second best.
        """
        return self._move(name, to_pinned=True)

    def unpin(self, name):
        """Back into the rolling pool - and into reach of the next prune."""
        return self._move(name, to_pinned=False)

    def _move(self, name, to_pinned):
        source = self._find(name, pinned=not to_pinned)

        if source is None:
            side = "pinned" if to_pinned is False else "rolling"
            raise FileNotFoundError(f"No {side} checkpoint named {name}")

        self.prepare()
        target = os.path.join(self.directory_for(to_pinned), name)

        shutil.move(source, target)

        return target

    def _find(self, name, pinned):
        for checkpoint in self.list(pinned=pinned):
            if checkpoint["name"] == name:
                return checkpoint["path"]

        return None

    def __repr__(self):
        return (
            f"CheckpointStore(dir={self.directory}, keep={self.keep}, "
            f"rolling={len(self.list(pinned=False))}, "
            f"pinned={len(self.list(pinned=True))})"
        )
