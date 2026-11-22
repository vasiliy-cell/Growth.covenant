"""Probe reward per evaluation episode for the 30 frozen-baseline worlds."""
import os, argparse, csv, json, statistics as st
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds
os.environ.setdefault('MPLCONFIGDIR', '/tmp/growth-matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def save(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--research-root', type=Path, default=Path.home() / 'Desktop/research')
    ap.add_argument('--output', type=Path, default=Path('baseline_overview'))
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    data = []
    worlds = []
    species = ('clons', 'mendel', 'non_linear')
    for sp in species:
        paths = sorted((args.research_root / 'logs/baseline_bad_frozen_1000' / sp).glob('*/run.json'))
        assert len(paths) == 10
        for p in paths:
            h = json.loads(p.read_text())
            session = h['sessions'][0]
            seed = session['seed']
            assert h['species'] == sp and session['config']['genome']['evolve'] == [] and session.get('finished_at')
            local = []
            for snap in sorted((p.parent / 'probe').glob('step_*')):
                step = int(snap.name[5:])
                episode = step / h['episode_length']
                values = []
                evaluated = []
                for a in sorted(snap.glob('*/run.json')):
                    j = json.loads(a.read_text())
                    s = j['sessions'][0]
                    assert s.get('finished_at') and j['probe']['world_id'] == h['world_id'] and (j['probe']['step'] == step)
                    evaluation_episodes = j['probe']['episodes']
                    assert evaluation_episodes == 20 and s['to_episode'] == 20 and (s['to_step'] == 400)
                    t = ds.dataset(str(a.parent / 'steps'), format='parquet').to_table(columns=['env_reward'])
                    assert t.num_rows == 400
                    values.append(sum(t['env_reward'].to_pylist()) / evaluation_episodes)
                    evaluated.append(evaluation_episodes)
                assert values
                row = dict(species=sp, seed=seed, snapshot_step=step, snapshot_episode=episode, checkpoint=int(episode // 100) * 100, probe_agents=len(values), reward_per_probe_episode=st.mean(values))
                data.append(row)
                local.append(row)
            assert local
            y = [r['reward_per_probe_episode'] for r in local]
            worlds.append(dict(species=sp, seed=seed, main_to_episode=session['to_episode'], survived_to_1000=session['to_step'] >= 20000, probe_snapshots=len(local), first_snapshot_episode=local[0]['snapshot_episode'], last_snapshot_episode=local[-1]['snapshot_episode']))
    save(out / 'probe_by_seed.csv', data)
    save(out / 'seed_summary.csv', worlds)
    lines = ['# Bad baseline \u0431\u0435\u0437 \u044d\u0432\u043e\u043b\u044e\u0446\u0438\u0438: probe overview', '', '**\u0415\u0434\u0438\u043d\u0438\u0446\u044b:** probe reward per episode = \u0441\u0443\u043c\u043c\u0430\u0440\u043d\u0430\u044f \u0432\u043d\u0435\u0448\u043d\u044f\u044f \u043d\u0430\u0433\u0440\u0430\u0434\u0430 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u0438\u0437\u043e\u043b\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0433\u043e \u0430\u0433\u0435\u043d\u0442\u0430 \u0437\u0430 20 probe-\u044d\u043f\u0438\u0437\u043e\u0434\u043e\u0432 / 20, \u0437\u0430\u0442\u0435\u043c \u0441\u0440\u0435\u0434\u043d\u0435\u0435 \u043f\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u043c \u0430\u0433\u0435\u043d\u0442\u0430\u043c \u0441\u043d\u0438\u043c\u043a\u0430. \u0413\u043e\u0440\u0438\u0437\u043e\u043d\u0442\u0430\u043b\u044c\u043d\u0430\u044f \u043e\u0441\u044c \u2014 \u044d\u043f\u0438\u0437\u043e\u0434\u044b \u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0433\u043e \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u044f; \u044d\u0442\u043e \u0434\u0440\u0443\u0433\u0430\u044f \u0448\u043a\u0430\u043b\u0430, \u0447\u0435\u043c 20 \u044d\u043f\u0438\u0437\u043e\u0434\u043e\u0432 \u0438\u0437\u043e\u043b\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0439 \u043e\u0446\u0435\u043d\u043a\u0438. \u0414\u043b\u044f \u0441\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u044f \u0441 \u043f\u0440\u0435\u0436\u043d\u0438\u043c\u0438 \u0442\u0430\u0431\u043b\u0438\u0446\u0430\u043c\u0438 \u0441\u0443\u043c\u043c\u0430\u0440\u043d\u043e\u0439 probe-\u043d\u0430\u0433\u0440\u0430\u0434\u044b \u044d\u0442\u0438 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f \u043d\u0443\u0436\u043d\u043e \u0443\u043c\u043d\u043e\u0436\u0438\u0442\u044c \u043d\u0430 20.', '', '\u0412\u0441\u0435 10 seeds \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043c\u0435\u0445\u0430\u043d\u0438\u0437\u043c\u0430 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b, \u0432 \u0442\u043e\u043c \u0447\u0438\u0441\u043b\u0435 \u0432\u044b\u043c\u0435\u0440\u0448\u0438\u0435 \u043c\u0438\u0440\u044b. \u041f\u043e\u0441\u043b\u0435 \u0432\u044b\u043c\u0438\u0440\u0430\u043d\u0438\u044f probe-\u043d\u0430\u0433\u0440\u0430\u0434\u0430 \u043d\u0435 \u043f\u043e\u0434\u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f \u043d\u0443\u043b\u0451\u043c: \u0434\u0430\u043b\u044c\u043d\u0435\u0439\u0448\u0438\u0445 \u0438\u0437\u043c\u0435\u0440\u0435\u043d\u0438\u0439 \u043d\u0435\u0442. \u0421\u0440\u0435\u0434\u043d\u0435\u0435 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043e\u043a\u043d\u0430 \u0432\u043a\u043b\u044e\u0447\u0430\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0438\u0437\u043c\u0435\u0440\u0435\u043d\u0438\u044f; \u043f\u043e\u044d\u0442\u043e\u043c\u0443 N \u043c\u043e\u0436\u0435\u0442 \u043c\u0435\u043d\u044f\u0442\u044c\u0441\u044f.', '', '\u0421\u043d\u0438\u043c\u043e\u043a \u0438\u043d\u043e\u0433\u0434\u0430 \u043f\u0435\u0440\u0435\u043d\u043e\u0441\u0438\u043b\u0441\u044f \u043d\u0430 20 \u044d\u043f\u0438\u0437\u043e\u0434\u043e\u0432 \u0438\u0437-\u0437\u0430 \u043d\u0435\u0445\u0432\u0430\u0442\u043a\u0438 \u0432\u0437\u0440\u043e\u0441\u043b\u044b\u0445. \u0422\u0430\u0431\u043b\u0438\u0446\u0430 \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u044f\u0435\u0442 \u043f\u043b\u0430\u043d\u043e\u0432\u0443\u044e \u0442\u043e\u0447\u043a\u0443 K \u0438 \u0435\u0451 rescue-\u0441\u043d\u0438\u043c\u043e\u043a K+20; \u0443\u043a\u0430\u0437\u0430\u043d\u044b \u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0434\u0438\u0430\u043f\u0430\u0437\u043e\u043d \u0438 N. \u041d\u0430 \u0433\u0440\u0430\u0444\u0438\u043a\u0430\u0445 \u043a\u0430\u0436\u0434\u0430\u044f seed-\u043a\u0440\u0438\u0432\u0430\u044f \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442 \u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u0432\u0440\u0435\u043c\u0435\u043d\u0430 \u0441\u043d\u0438\u043c\u043a\u043e\u0432.', '']
    stats = {}
    for sp in species:
        rr = [r for r in data if r['species'] == sp]
        ww = [w for w in worlds if w['species'] == sp]
        stats[sp] = dict(seeds=10, survived=sum((w['survived_to_1000'] for w in ww)))
        lines += ['## ' + sp, '', f"\u0414\u043e\u0448\u043b\u0438 \u0434\u043e 1000 \u044d\u043f\u0438\u0437\u043e\u0434\u043e\u0432: **{stats[sp]['survived']}/10**.", '', '| \u041f\u043b\u0430\u043d\u043e\u0432\u044b\u0439 \u044d\u043f\u0438\u0437\u043e\u0434 | \u0424\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u044d\u043f\u0438\u0437\u043e\u0434\u044b \u0441\u043d\u0438\u043c\u043a\u043e\u0432 | N seeds | \u0421\u0440\u0435\u0434\u043d\u044f\u044f probe-\u043d\u0430\u0433\u0440\u0430\u0434\u0430 \u0437\u0430 \u044d\u043f\u0438\u0437\u043e\u0434 |', '| --- | --- | ---: | ---: |']
        means = []
        for checkpoint in range(100, 1001, 100):
            group = [r for r in rr if r['checkpoint'] == checkpoint]
            if not group:
                lines.append(f'| {checkpoint} | \u2014 | 0 | \u2014 |')
                continue
            assert len({r['seed'] for r in group}) == len(group)
            times = [r['snapshot_episode'] for r in group]
            m = st.mean((r['reward_per_probe_episode'] for r in group))
            means.append((st.mean(times), m))
            lines.append(f'| {checkpoint} | {min(times):.0f}\u2013{max(times):.0f} | {len(group)} | {m:.3f} |')
        (fig, ax) = plt.subplots(figsize=(11, 6), layout='constrained')
        colors = plt.get_cmap('tab10')
        for (i, w) in enumerate(sorted(ww, key=lambda w: w['seed'])):
            seed = w['seed']
            g = sorted([r for r in rr if r['seed'] == seed], key=lambda r: r['snapshot_step'])
            label = str(seed) + (f" (extinct ep {w['main_to_episode']})" if not w['survived_to_1000'] else '')
            ax.plot([r['snapshot_episode'] for r in g], [r['reward_per_probe_episode'] for r in g], marker='o', ms=3, lw=1.2, alpha=0.8, label=label, color=colors(i))
        ax.set(title=f'{sp}: frozen bad baseline, all 10 seeds', xlabel='Main-world episode at probe snapshot', ylabel='Mean probe reward per evaluation episode', xlim=(80, 1020))
        ax.grid(alpha=0.25)
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=8)
        for ext in ('svg',):
            fig.savefig(out / f'probe_all_seeds_{sp}.{ext}', dpi=200)
        plt.close(fig)
        lines += ['', f'![{sp}](probe_all_seeds_{sp}.svg)', '']
    (out / 'overview.md').write_text('\n'.join(lines) + '\n')
    (out / 'summary.json').write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
if __name__ == '__main__':
    main()
