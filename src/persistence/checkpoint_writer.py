import os

import torch


class CheckpointWriter:
    """
    Owns where the minds of a population live on disk.

    One file per agent, filed under the run it belonged to:

        <models_dir>/<run_id>/<agent_id>.pth

    Agent ids are globally unique (src/Agent/identity.py), so a file is
    never overwritten by a later run and the whole population of one
    experiment stays together in one directory - which is what makes a
    year of experiments something you can go back through.

    What goes in is a record of an individual, not a bare state_dict. Weights
    alone cannot tell you whether you are holding a cautious veteran or a
    reckless newborn, and cannot be continued as either.

    The Adam state is deliberately left out: it doubles the file and only
    means anything when the exact same optimisation is resumed, never when
    a brain is inherited.

    Nothing reads these files back yet - continuing an earlier run is its
    own feature. They are already worth writing: a dead agent's mind exists
    nowhere else once it is dropped.
    """

    def __init__(self, models_dir, run_id):
        self.models_dir = models_dir
        self.run_id = run_id
        self.directory = os.path.join(models_dir, run_id)

    def path_for(self, agent_id):
        return os.path.join(self.directory, f"{agent_id}.pth")

    def save(self, agent_id, brain):
        """Writes one mind down and returns the path it went to."""
        os.makedirs(self.directory, exist_ok=True)

        record = {
            "agent_id": agent_id,
            "run_id": self.run_id,
        }
        record.update(brain.state())

        path = self.path_for(agent_id)
        torch.save(record, path)

        return path

    def save_all(self, brains):
        """Writes down every mind still alive at the end of the run."""
        return [
            self.save(agent_id, brain)
            for agent_id, brain in brains.items()
        ]
