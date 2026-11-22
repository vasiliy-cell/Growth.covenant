#!/usr/bin/env python3
"""Rebuild common-seed comparisons and age plots from local raw logs.
Usage: python common_seeds_and_age.py --research-root ~/Desktop/research --output ./analysis
Dependencies: numpy, pyarrow, matplotlib.
"""
import argparse, csv, json, math, statistics as st, os
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds
os.environ.setdefault('MPLCONFIGDIR','/tmp/growth-matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def betacf(a, b, x):
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1 / d
    h = d
    for m in range(1, 300):
        aa = m * (b - m) * x / ((qam + 2 * m) * (a + 2 * m))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < 1e-300:
            d = 1e-300
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + 2 * m) * (qap + 2 * m))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < 1e-300:
            d = 1e-300
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-14:
            return h
    raise ValueError('beta did not converge')

def ibeta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    return bt * betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * betacf(b, a, 1 - x) / b

def tc(df):
    (lo, hi) = (0.0, 100.0)
    for _ in range(90):
        mid = (lo + hi) / 2
        p = 1 - 0.5 * ibeta(df / 2, 0.5, df / (df + mid * mid))
        if p < 0.975:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def rank(x):
    x=np.asarray(x);order=np.argsort(x,kind='stable');r=np.empty(len(x),float);i=0
    while i<len(x):
        j=i+1
        while j<len(x) and x[order[j]]==x[order[i]]:j+=1
        r[order[i:j]]=(i+j-1)/2;i=j
    return r

def corr(x,y,spearman=False):
    if spearman:x,y=rank(x),rank(y)
    if np.std(x)==0 or np.std(y)==0:return float('nan')
    return float(np.corrcoef(x,y)[0,1])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('common_seeds_analysis'));args=ap.parse_args();root=args.research_root.expanduser();out=args.output;out.mkdir(parents=True,exist_ok=True)
    species=('clons','mendel','non_linear');worlds={s:{} for s in species};agents=[];worldrows=[]
    for sp in species:
        for d in sorted((root/'logs/probe'/sp).glob('seed-*')):
            h=json.loads((d/'run.json').read_text());seed=h['sessions'][0]['seed'];assert d.name=='seed-'+str(seed) and h['species']==sp and seed not in worlds[sp]
            pop=ds.dataset(str(d/'episodes/population'),format='parquet').to_table(columns=['step_end','agents'],filter=ds.field('step_end')==40000).to_pylist()
            if not pop or pop[-1]['agents']<=0:continue
            snaps=sorted([p for p in (d/'probe').glob('step_*') if int(p.name[5:])<=40000],key=lambda p:int(p.name[5:]))[-3:]
            if len(snaps)!=3:raise ValueError('Missing snapshots: '+str(d))
            steps=[int(p.name[5:]) for p in snaps]
            tab=ds.dataset(str(d/'episodes/agents'),format='parquet').to_table(columns=['step_end','agent_id','age'],filter=ds.field('step_end').isin(steps)).to_pylist()
            ages={(x['step_end'],x['agent_id']):x['age'] for x in tab};values=[];meanages=[];local=[]
            for snap,step in zip(snaps,steps):
                av=[];aa=[]
                for p in sorted(snap.glob('*/run.json')):
                    j=json.loads(p.read_text());aid=j['probe']['agent_id'];assert j['probe']['step']==step and j['probe']['world_id']==h['world_id'];age=ages[(step,aid)]
                    t=ds.dataset(str(p.parent/'steps'),format='parquet').to_table(columns=['env_reward']);assert t.num_rows==400
                    reward=math.fsum(t['env_reward'].to_pylist());av.append(reward);aa.append(age)
                    local.append(dict(species=sp,seed=seed,world_id=h['world_id'],snapshot_step=step,snapshot_episode=step/20,agent_id=aid,age_steps=age,probe_reward=reward))
                assert av;values.append(st.mean(av));meanages.append(st.mean(aa))
            v=st.mean(values);age=st.mean(meanages);worlds[sp][seed]=v;agents+=local;worldrows.append(dict(species=sp,seed=seed,mean_age_steps=age,probe_reward=v,measurements=len(local)))
    common=sorted(set.intersection(*(set(worlds[s]) for s in species)));assert common
    table=[dict(seed=s,clons=worlds['clons'][s],mendel=worlds['mendel'][s],non_linear=worlds['non_linear'][s]) for s in common]
    write_csv(out/'common_seeds.csv',table);write_csv(out/'probe_agent_ages.csv',agents);write_csv(out/'probe_world_ages.csv',worldrows)
    lines=['# Три механизма на одном наборе seeds','',f'Общих seeds: **{len(common)}**. Все три мира дожили до 2000 эпизодов и имеют три probe-снимка не позже шага 40000. Метрика каждого мира — среднее по агентам внутри снимка, затем по последним трём снимкам.','', '| seed | clons | mendel | non_linear |','| --- | ---: | ---: | ---: |']
    for r in table:lines.append(f'| {r["seed"]} | {r["clons"]:.3f} | {r["mendel"]:.3f} | {r["non_linear"]:.3f} |')
    pairs=[('mendel','clons'),('non_linear','clons'),('non_linear','mendel')];stats={};diffrows=[]
    fig,axs=plt.subplots(3,1,figsize=(11,9),layout='constrained')
    for ax,(a,b) in zip(axs,pairs):
        diff=np.array([worlds[a][s]-worlds[b][s] for s in common]);n=len(diff);mean=float(diff.mean());median=float(np.median(diff));sd=float(diff.std(ddof=1));sem=sd/math.sqrt(n);moe=tc(n-1)*sem
        key=a+' - '+b;stats[key]=dict(n=n,mean=mean,median=median,sd=sd,sem=sem,moe=moe,ci=[mean-moe,mean+moe],positive=int((diff>0).sum()),negative=int((diff<0).sum()),zero=int((diff==0).sum()))
        for s,v in zip(common,diff):diffrows.append(dict(pair=key,seed=s,difference=float(v)))
        lines+=['',f'## {a} − {b}','','| Метрика | Значение |','| --- | ---: |',f'| n | {n} |',f'| Среднее | {mean:+.3f} |',f'| Медиана | {median:+.3f} |',f'| SD | {sd:.3f} |',f'| SEM | {sem:.3f} |',f'| MoE 95% | ±{moe:.3f} |',f'| 95% CI | [{mean-moe:+.3f}; {mean+moe:+.3f}] |',f'| Разность > 0 / < 0 / = 0 | {int((diff>0).sum())} / {int((diff<0).sum())} / {int((diff==0).sum())} |']
        y=np.linspace(-.18,.18,n);ax.scatter(diff,y,s=30,c=np.where(diff>=0,'#287baf','#bc5555'),alpha=.85);ax.axvline(0,color='black',lw=1)
        ax.axvline(mean,color='#7d3bb5',lw=2,label=f'Mean {mean:+.1f}');ax.axvline(median,color='#d58b19',ls='--',lw=2,label=f'Median {median:+.1f}')
        ax.set(title=f'{a} - {b} | n={n}',xlabel='Probe reward difference (right: first mechanism wins)',yticks=[],ylim=(-.35,.35));ax.legend(loc='upper left');ax.grid(axis='x',alpha=.2)
    for ext in ('png','svg','pdf'):fig.savefig(out/('paired_differences.'+ext),dpi=200)
    plt.close(fig);write_csv(out/'paired_differences.csv',diffrows)
    lines+=['','CI рассчитаны обычным парным t-интервалом, без поправок на несколько сравнений и последовательный просмотр данных. Выборка условна на выживании всех трёх механизмов. Точки графика — существующие разности этих же строк, нового статистического сравнения график не вводит.','','![Разности по seeds](paired_differences.png)']
    (out/'common_three_results.md').write_text('\n'.join(lines)+'\n');(out/'common_three_stats.json').write_text(json.dumps(stats,indent=2))
    age_lines=['# Возраст и probe-награда','', 'Основная выборка: все доступные probe-миры каждого механизма, дожившие до 2000 эпизодов; последние три снимка ≤40000 шагов. Это более широкая выборка, чем пересечение трёх видов. Возраст взят из основного мира по agent_id и шагу снимка, в шагах жизни; возраст из изолированного probe не используется.','', 'Один агент может встречаться в нескольких снимках. Поэтому отдельные агент-снимки не считаются независимыми репликами; их корреляции только описательные. Для основной оценки связи каждый seed представлен одной точкой: средний возраст выбранных агентов и средняя probe-награда по трём снимкам. Интервал корреляции получен bootstrap-перевыборкой целых seeds (2000 повторов, фиксированный RNG).','', '| Вид | Миров | Агент-снимков | Возраст Q25 | Медиана | Q75 | Средний возраст |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained');colors=['#2676ac','#d27c20','#439355'];correlations=[]
    scatter,axs=plt.subplots(1,3,figsize=(15,4.5),layout='constrained');rng=np.random.default_rng(20261114)
    for sp,col,ax in zip(species,colors,axs):
        ar=[r for r in agents if r['species']==sp];wr=[r for r in worldrows if r['species']==sp];ages=np.array([r['age_steps'] for r in ar]);rewards=np.array([r['probe_reward'] for r in ar]);x=np.array([r['mean_age_steps'] for r in wr]);y=np.array([r['probe_reward'] for r in wr]);q=np.quantile(ages,[.25,.5,.75]);age_lines.append(f'| {sp} | {len(wr)} | {len(ar)} | {q[0]:.1f} | {q[1]:.1f} | {q[2]:.1f} | {ages.mean():.1f} |')
        axes[0].hist(ages,bins=np.arange(0,max(r['age_steps'] for r in agents)+200,200),density=True,histtype='step',lw=2,label=sp,color=col)
        ordered=np.sort(ages);axes[1].plot(ordered,np.arange(1,len(ages)+1)/len(ages),label=sp,color=col)
        ax.scatter(ages,rewards,s=8,alpha=.12,color=col,label='Agent-snapshot');ax.scatter(x,y,s=24,color=col,edgecolors='black',linewidths=.3,label='Seed mean');ax.set(title=sp,xlabel='Age in main-world steps',ylabel='Probe reward');ax.legend(fontsize=8)
        boots=[]
        for _ in range(2000):
            ix=rng.integers(0,len(x),len(x));boots.append(corr(x[ix],y[ix]))
        ci=np.nanquantile(boots,[.025,.975]);correlations.append(dict(species=sp,n_worlds=len(wr),n_agent_snapshots=len(ar),individual_pearson=corr(ages,rewards),individual_spearman=corr(ages,rewards,True),world_pearson=corr(x,y),world_spearman=corr(x,y,True),world_pearson_ci=list(ci)))
    for ax in axes:ax.set_xlabel('Age in main-world steps');ax.legend();ax.grid(alpha=.2)
    axes[0].set_ylabel('Density');axes[1].set_ylabel('Cumulative fraction')
    for ext in ('png','svg','pdf'):fig.savefig(out/('age_distributions.'+ext),dpi=200);scatter.savefig(out/('age_reward.'+ext),dpi=200)
    plt.close('all');age_lines+=['','## Связь возраста с наградой','','| Вид | Pearson, агент-снимки | Spearman, агент-снимки | Pearson, средние seeds | Bootstrap 95% CI Pearson | Spearman, средние seeds |','| --- | ---: | ---: | ---: | --- | ---: |']
    for r in correlations:age_lines.append(f'| {r["species"]} | {r["individual_pearson"]:+.3f} | {r["individual_spearman"]:+.3f} | {r["world_pearson"]:+.3f} | [{r["world_pearson_ci"][0]:+.3f}; {r["world_pearson_ci"][1]:+.3f}] | {r["world_spearman"]:+.3f} |')
    age_lines+=['','Корреляция не устанавливает причинность: возраст, отбор выживших, состав популяции и эволюция генов могут влиять совместно. Этот анализ не корректирует основное сравнение механизмов на возраст. Bootstrap CI исследовательские, без поправки на множественные проверки.','','![Возраст](age_distributions.png)','','![Возраст и награда](age_reward.png)']
    (out/'probe_age_analysis.md').write_text('\n'.join(age_lines)+'\n');(out/'age_correlations.json').write_text(json.dumps(correlations,indent=2));print(json.dumps({'common_seeds':len(common),'pairs':stats,'age':correlations},indent=2))

if __name__=='__main__':main()
