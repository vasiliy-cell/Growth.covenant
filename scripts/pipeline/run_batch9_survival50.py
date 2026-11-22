#!/usr/bin/env python3
"""Run the fixed Batch 9 on the server; no dependency on the Mac."""
import concurrent.futures as cf
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.ai/pipeline/batch9-survival50'
SPECIES = ('clons', 'mendel', 'non_linear')
EVOLVE = 'genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]'


def main():
    os.chdir(ROOT)
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / 'runner.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (STATE / 'status.json').exists():
        raise SystemExit('Batch 9 already started; refusing a duplicate launch')
    seeds = [int(s) for s in (ROOT / 'scripts/pipeline/seeds_batch9.txt').read_text().split()]
    assert len(seeds) == len(set(seeds)) == 50
    used = set()
    for p in (ROOT / 'logs').glob('*/*/run.json'):
        used.update(s['seed'] for s in json.loads(p.read_text())['sessions'])
    assert not used.intersection(seeds), 'New seeds overlap an existing server world'
    parallel = min(16, len(os.sched_getaffinity(0)))
    state = dict(started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 state='running', parallel=parallel, episodes=500, probe=False,
                 seeds=seeds, config_sha256=hashlib.sha256((ROOT / 'config.yml').read_bytes()).hexdigest(),
                 results=[], active_species=None)

    def save():
        tmp = STATE / 'status.json.tmp'
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(STATE / 'status.json')

    def run_one(species, idx, seed):
        series = 'batch9-survival50-' + species
        console = ROOT / '.ai/pipeline' / series / 'console'
        console.mkdir(parents=True, exist_ok=True)
        cmd = [str(ROOT / '.venv/bin/python'), 'src/run.py', '--episodes', '500',
               '--seed', str(seed), '--agents', '20', '--species', species,
               '--set', EVOLVE,
               '--set', 'genome.genes.gamma.mean=0.5', '--set', 'genome.genes.gamma.scale=0.2',
               '--set', 'genome.genes.hidden_size.mean=40', '--set', 'genome.genes.buffer_size.mean=1000',
               '--set', 'checkpoints.keep=200', '--set', 'checkpoints.every_steps=0',
               '--label', f'{series}-s{idx:02d}', '--series', series,
               '--resume', '', '--no-pin', '--no-probe']
        env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONPATH='.')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (console / f's{idx:02d}_{seed}.log').open('w') as log:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                  stderr=subprocess.STDOUT, env=env, check=False)
        return dict(species=species, seed=seed, index=idx, exit=proc.returncode,
                    started_at=started, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())

    save()
    for species in SPECIES:
        state['active_species'] = species
        save()
        with cf.ThreadPoolExecutor(max_workers=parallel) as pool:
            jobs = [pool.submit(run_one, species, idx, seed) for idx, seed in enumerate(seeds, 1)]
            for job in cf.as_completed(jobs):
                result = job.result()
                state['results'].append(result)
                save()
                series = 'batch9-survival50-' + species
                with (ROOT / '.ai/pipeline' / series / 'done.txt').open('a') as done:
                    done.write(f'{result["finished_at"]} seed {result["seed"]} exit {result["exit"]}\n')
                print(json.dumps(result), flush=True)
    state['active_species'] = None
    state['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state['state'] = 'complete' if all(r['exit'] == 0 for r in state['results']) else 'failed'
    save()
    if state['state'] != 'complete':
        raise SystemExit('Batch finished with errors; inspect status.json and console logs')
    print('BATCH9 COMPLETE: 150/150 successful', flush=True)


if __name__ == '__main__':
    main()
