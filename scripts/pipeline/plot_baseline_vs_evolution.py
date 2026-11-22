#!/usr/bin/env python3
"""Matched-seed frozen baseline versus evolution probe curves, up to ep1000."""
import argparse,csv,json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/growth-matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pyarrow.dataset as ds
import math


def measurements(world,sp,seed,condition):
    header=json.loads((world/'run.json').read_text());assert header['species']==sp and header['sessions'][0]['seed']==seed
    rows=[]
    for snap in sorted((world/'probe').glob('step_*')):
        step=int(snap.name[5:]);episode=step/header['episode_length']
        if episode>1000:continue
        vals=[]
        for p in sorted(snap.glob('*/run.json')):
            h=json.loads(p.read_text());assert h['probe']['world_id']==header['world_id'] and h['probe']['step']==step
            assert h['probe']['episodes']==20 and h['sessions'][0]['to_step']==400 and h['sessions'][0].get('finished_at')
            t=ds.dataset(str(p.parent/'steps'),format='parquet').to_table(columns=['env_reward']);assert t.num_rows==400
            vals.append(math.fsum(t['env_reward'].to_pylist())/20)
        assert vals
        rows.append(dict(species=sp,seed=seed,condition=condition,main_episode=episode,reward_per_probe_episode=sum(vals)/len(vals),agents=len(vals),world_id=header['world_id']))
    return header,rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('baseline_vs_evolution'));args=ap.parse_args();root=args.research_root;out=args.output;out.mkdir(parents=True,exist_ok=True)
    species=('clons','mendel','non_linear');allrows=[];seedsets={};records=[]
    for sp in species:
        seeds={}
        for p in (root/'logs/baseline_bad_frozen_1000'/sp).glob('*/run.json'):
            h=json.loads(p.read_text());s=h['sessions'][0]['seed'];assert s not in seeds;seeds[s]=p.parent
        assert len(seeds)==10;seedsets[sp]=set(seeds)
        for seed,baseline in sorted(seeds.items()):
            evo=root/'logs/probe'/sp/('seed-'+str(seed));assert evo.is_dir()
            bh,br=measurements(baseline,sp,seed,'Frozen baseline');eh,er=measurements(evo,sp,seed,'Evolution enabled')
            bc,ec=bh['sessions'][0]['config'],eh['sessions'][0]['config'];assert bc['genome']['evolve']==[] and ec['genome']['evolve']
            for k in ('run','agents','world','reward_shaping','energy','life','probe'):assert bc[k]==ec[k],(sp,seed,k)
            assert bc['genome']['genes']==ec['genome']['genes']
            assert br
            allrows+=br+er
            records.append(dict(species=sp,seed=seed,baseline_world=bh['world_id'],evolution_world=eh['world_id'],baseline_snapshots=len(br),evolution_snapshots=len(er)))
    assert seedsets['clons']==seedsets['mendel']==seedsets['non_linear']
    with (out/'curve_values.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
    (out/'matched_worlds.json').write_text(json.dumps(records,indent=2))
    markers=['o','v','^','<','>','s','P','D','X','*'];seeds=sorted(seedsets['clons']);top=max(r['reward_per_probe_episode'] for r in allrows)*1.08;bottom=min(0,min(r['reward_per_probe_episode'] for r in allrows)*1.08)
    for sp in species:
        fig,ax=plt.subplots(figsize=(12,6.5),layout='constrained')
        for seed,marker in zip(seeds,markers):
            for condition,color in [('Frozen baseline','black'),('Evolution enabled','#cf2525')]:
                rows=sorted([r for r in allrows if r['species']==sp and r['seed']==seed and r['condition']==condition],key=lambda r:r['main_episode'])
                ax.plot([r['main_episode'] for r in rows],[r['reward_per_probe_episode'] for r in rows],color=color,alpha=.65,lw=1.3,marker=marker,ms=3.5)
        ax.set(title=f'{sp}: frozen bad baseline vs evolution | 10 matched seeds',xlabel='Main-world episode at probe snapshot',ylabel='Mean probe reward per evaluation episode',xlim=(80,1020),ylim=(bottom,top));ax.grid(alpha=.2)
        missing=[str(r['seed']) for r in records if r['species']==sp and r['evolution_snapshots']==0]
        if missing:ax.text(.01,.01,'Evolution: no probe samples for seed(s) '+', '.join(missing),transform=ax.transAxes,fontsize=8,va='bottom')
        condition_legend=ax.legend(handles=[Line2D([0],[0],color='black',label='Frozen baseline'),Line2D([0],[0],color='#cf2525',label='Evolution enabled')],loc='upper left');ax.add_artist(condition_legend)
        ax.legend(handles=[Line2D([0],[0],color='black',marker=m,ls='None',label=str(s),ms=5) for s,m in zip(seeds,markers)],title='Seed (same marker in both conditions)',loc='center left',bbox_to_anchor=(1,.5),fontsize=8,title_fontsize=8)
        for ext in ('svg','png','pdf'):fig.savefig(out/f'baseline_vs_evolution_{sp}.{ext}',dpi=200)
        plt.close(fig)
    lines=['# Baseline vs evolution: matched seeds','', 'Three graphs, 10 matched seeds per reproduction mechanism. Black: frozen bad baseline. Red: evolution enabled. Matching markers identify the same seed in both conditions. No averaging across seeds is shown.','', 'X: actual main-world episode of the probe snapshot, limited to episode 1000 in both conditions. Y: mean external reward per isolated evaluation episode (total reward over 20 probe episodes, divided by 20, then averaged across the agents of that snapshot). Multiply Y by 20 to recover the total-probe-reward units of the older research tables.','', 'Curves stop at their last available measurement. Extinct worlds are included; missing snapshots are not replaced with zero and are not interpolated as observations. Lines connect available observations. Snapshots delayed by the adult-rescue rule use their actual episode, e.g. 120 instead of 100.','', 'The same world settings and gene-distribution specifications were verified in both conditions. With evolution disabled, founders receive the fixed gene means; with evolution enabled, founders are drawn from the configured distributions. Thus these conditions differ in initial genetic variation as well as subsequent genetic evolution.','', 'CSV: curve_values.csv. Exact source-world identities: matched_worlds.json. Reproduce with the supplied plot_baseline_vs_evolution.py script and the local logs.']
    lines+=['','| Mechanism | Baseline curves | Evolution curves with measurements |','| --- | ---: | ---: |']
    for sp in species:lines.append(f'| {sp} | 10 | {sum(r["evolution_snapshots"]>0 for r in records if r["species"]==sp)} |')
    lines+=['','If a world has no probe measurements, no curve can be drawn for it; its seed remains in matched_worlds.json and is identified on the graph.']
    for sp in species:lines+=['',f'![{sp}](baseline_vs_evolution_{sp}.svg)']
    (out/'README.md').write_text('\n'.join(lines)+'\n');print('Verified 30 matched world pairs; generated 3 matched-seed graphs; rows:',len(allrows))

if __name__=='__main__':main()
