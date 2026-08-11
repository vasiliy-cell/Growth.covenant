"""
The run is one continuous process now, so one log file = one RUN, not one
episode. An episode is just a logging window, and every step line carries its
window index in the `episode` field.

Everything that used to derive "per episode" values from "per file" values
should group steps with the helpers below instead.
"""

import json
import os

LOG_DIR = "logs"


def iter_steps(files, log_dir=LOG_DIR):
    """Yields (file, step_record) for every step line of the given files."""
    for file in files:
        path = os.path.join(log_dir, file)

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)

                if data.get("type") == "step":
                    yield file, data


def group_steps_by_episode(files, log_dir=LOG_DIR):
    """
    Returns [((file, episode_index), [step, ...]), ...] in the order the
    windows appear in the logs.

    Old logs (one episode per file, no `episode` field) fall back to a single
    group per file, which reproduces the previous behaviour.
    """
    groups = {}
    order = []

    for file, data in iter_steps(files, log_dir):
        key = (file, data.get("episode", 0))

        if key not in groups:
            groups[key] = []
            order.append(key)

        groups[key].append(data)

    return [(key, groups[key]) for key in order]
