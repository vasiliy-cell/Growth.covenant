#!/usr/bin/env python3
"""Mean population of worlds extinct by episode 500; zero after extinction."""
import argparse,csv,json,os
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds
os.environ.setdefault('MPLCONFIGDIR','/tmp/growth-matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('extinct_population'));args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True);curves={s:[] for s in ('clons','mendel','non_linear')};cohort=[];seen=set()
    for p in sorted((args.research_root/'logs').glob('*/*/seed-*/run.json')):
        h=json.loads(p.read_text());assert len(h['sessions'])==1;session=h['sessions'][0];sp=h['species'];seed=session['seed'];assert (sp,seed) not in seen;seen.add((sp,seed));assert h['episode_length']==20 and session.get('finished_at')
        if session['to_step']>10000:continue
        d=p.parent;delta=np.zeros(10001,dtype=np.int64)
        for folder,sign in [('births',1),('deaths',-1)]:
            files=sorted((d/'events'/folder).glob('*.parquet'))
            if files:
                steps=ds.dataset([str(f) for f in files],format='parquet').to_table(columns=['step'],filter=ds.field('step')<=10000)['step'].to_numpy();np.add.at(delta,steps,sign)
        population=np.cumsum(delta);assert population[0]==20 and population.min()>=0
        if population[session['to_step']]!=0:continue
        assert np.all(population[session['to_step']:]==0)
        curves[sp].append(population[::20]);cohort.append(dict(species=sp,seed=seed,world_id=h['world_id'],extinction_step=session['to_step'],extinction_episode=session['to_step']/20))
    assert len(seen)==1000
    with (out/'extinct_worlds.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cohort[0]));w.writeheader();w.writerows(cohort)
    means={sp:np.mean(values,axis=0) for sp,values in curves.items()};assert all(len(v) for v in curves.values());x=np.arange(501);top=max(max(v) for v in means.values())*1.08
    colors={'clons':'#2676ac','mendel':'#d27c20','non_linear':'#439355'}
    for sp in curves:
        fig,ax=plt.subplots(figsize=(9,5),layout='constrained');ax.plot(x,means[sp],lw=2,color=colors[sp]);ax.set(xlabel='Main-world episode',ylabel='Mean population size',title=f'{sp}: worlds extinct by episode 500 (n={len(curves[sp])})',xlim=(0,500),ylim=(0,top));ax.grid(alpha=.25)
        for ext in ('png','svg','pdf'):fig.savefig(out/f'extinct_population_{sp}.{ext}',dpi=200)
        plt.close(fig)
    with (out/'mean_population.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['episode',*curves]);w.writerows([int(ep),*[float(means[s][ep]) for s in curves]] for ep in x)
    lines=['# Средняя численность в вымерших мирах','', 'Горизонт: 500 эпизодов. Отобраны миры, которые вымерли не позже шага 10000. Все траектории выровнены по началу запуска, а не по моменту смерти. После вымирания численность равна нулю; знаменатель среднего фиксирован. Поэтому средняя кривая к 500-му эпизоду достигает нуля.','', 'Численность восстановлена по событиям рождения и смерти, включая новорождённых. На графике показаны значения на границах эпизодов (20 шагов); исходное начало — 20 агентов. Вертикальная шкала одинакова на всех трёх графиках. Это численность, а не скорость её изменения.','', '| Механизм | Вымерших миров до ep500 |','| --- | ---: |']
    for sp in curves:lines.append(f'| {sp} | {len(curves[sp])} |')
    lines+=['', 'Графики описывают именно выборку вымерших миров. Миры, выжившие к эпизоду 500, сюда не включены, даже если они вымерли позже.']
    for sp in curves:lines+=['',f'![{sp}](extinct_population_{sp}.png)']
    (out/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps({sp:len(v) for sp,v in curves.items()}))

if __name__=='__main__':main()
