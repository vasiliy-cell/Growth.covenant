"""
The panel reads a world again every few seconds; it must not read it twice
when nothing was written, and it must never serve what is no longer true.

Both halves matter. Without the first, an open page costs a second of CPU
per refresh on a long run. Without the second, a running world looks frozen.
"""

import os

from src.persistence.run_log import RunLog
from src.UI import reports


def write_window(directory, rows, run_id):
    log = RunLog(
        directory=directory,
        world_id="cache-test",
        run_id=run_id,
        seed=1,
        episode_length=20,
        config={},
        species="clons",
        gene_names=["alpha"],
    )

    for step in range(rows):
        log.log_step(
            step=step, agent_id="a-0000", position=(1, 1), action=0,
            env_reward=1.0, intrinsic_reward=0.0, shaped_reward=1.0,
            energy=10.0, age=step,
        )

    log.end_episode(
        step=rows,
        agents={"a-0000": {"epsilon": 0.1, "curiosity_beta": 0.1, "energy": 10.0, "age": rows}},
        non_empty_ratio=0.3,
    )
    log.close()

    return log


def test_a_table_is_read_once_until_it_changes(tmp_path):
    logs = os.path.join(tmp_path, "logs")
    log = write_window(logs, 20, "first")

    from src.persistence.log_reader import RunLogReader

    reader = RunLogReader(log.path)
    once = reports.read(reader, "episode_population")

    # Nothing has been written: the same table comes back, not a new read.
    assert reports.read(reader, "episode_population") is once

    write_window(logs, 20, "second")

    grown = reports.read(RunLogReader(log.path), "episode_population")
    assert grown is not once
    assert grown.num_rows == once.num_rows + 1


def test_the_catalog_notices_a_world_that_grew(tmp_path):
    logs = os.path.join(tmp_path, "logs")
    write_window(logs, 20, "first")

    before = reports.catalog(logs)[0]
    assert reports.catalog(logs)[0]["episodes"] == before["episodes"]

    write_window(logs, 40, "second")

    after = reports.catalog(logs)[0]
    assert after["episodes"] == before["episodes"] + 1
    assert after["size"] > before["size"]
