#!/usr/bin/env python3
"""World-level recovery after population <10, reaching >=70 by episode 500."""
import argparse,collections,csv,json
from pathlib import Path
import pyarrow.dataset as ds

def read(folder,columns,horizon):
    files=sorted(folder.glob('*.parquet'))
    if not files:return []
    return ds.dataset([str(p) for p in files],format='parquet').to_table(columns=columns,filter=ds.field('step')<=horizon).to_pylist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--low-threshold',type=int,default=10);ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('recovery_analysis'));args=ap.parse_args();root=args.research_root;out=args.output;out.mkdir(parents=True,exist_ok=True)
    results=[];seen=set();checks=0
    for header in sorted((root/'logs').glob('*/*/seed-*/run.json')):
        h=json.loads(header.read_text());assert len(h['sessions'])==1 and h['sessions'][0].get('finished_at');sp=h['species'];seed=h['sessions'][0]['seed'];key=(sp,seed);assert key not in seen;seen.add(key)
        horizon=500*h['episode_length'];assert h['episode_length']==20
        d=header.parent;delta=collections.Counter();births=collections.Counter()
        for row in read(d/'events/births',['step'],horizon):delta[row['step']]+=1;births[row['step']]+=1
        for row in read(d/'events/deaths',['step'],horizon):delta[row['step']]-=1
        assert delta[0]==h['sessions'][0]['config']['agents']['count']==20
        poprows=ds.dataset(str(d/'episodes/population'),format='parquet').to_table(columns=['step_end','agents']).to_pylist();reference={r['step_end']:r['agents'] for r in poprows if r['step_end']<=horizon}
        n=0;dip=None;recovered=None
        for step in sorted(set(delta)|set(reference)):
            n+=delta[step];assert n>=0
            if step in reference:
                assert n-births[step]==reference[step],(str(d),step,n,births[step],reference[step]);checks+=1
            if dip is None and step>0 and n<args.low_threshold:dip=step
            if dip is not None and recovered is None and step>dip and n>=70:recovered=step
        results.append(dict(species=sp,seed=seed,world_id=h['world_id'],group=d.parents[1].name,first_below_threshold_step=dip,recovery_to_70_step=recovered,dipped=dip is not None,recovered=recovered is not None,observed_until_step=min(horizon,h['sessions'][0]['to_step'])))
    assert len(results)==1000
    with (out/'world_recovery.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    lines=['# Восстановление популяции до 500 эпизодов','', 'Все 1000 миров, включая вымершие. Численность восстановлена после каждого полного шага по событиям рождения и смерти и сверена с основными логами популяции с учётом новорождённых: в строке population агенты, родившиеся на этом же шаге, ещё не имеют brain и пропускаются. Здесь они включены в фактическую численность. Начальная численность — 20.','', 'Мир включается в знаменатель, если хотя бы раз численность стала <10. Восстановление = после первого такого события мир хотя бы раз достиг ≥70, не позже шага 10000 (500 эпизодов). Каждый мир учитывается один раз. Достижение 70 до падения не считается восстановлением; повторное вымирание после восстановления не отменяет состоявшееся восстановление.','', '| Механизм | Восстановились / падали ниже 10 | Доля восстановившихся |','| --- | ---: | ---: |'];summary={}
    for sp in ('clons','mendel','non_linear'):
        rs=[r for r in results if r['species']==sp];eligible=sum(r['dipped'] for r in rs);ok=sum(r['recovered'] for r in rs);pct=100*ok/eligible
        summary[sp]=dict(total_worlds=len(rs),dipped=eligible,recovered=ok,percent=pct);lines.append(f'| {sp} | {ok}/{eligible} | {pct:.2f}% |')
    lines+=['','Это наблюдаемая доля до общего срока 500 эпизодов: у миров с поздним падением было меньше времени на восстановление. Статистическая значимость различий здесь не проверяется.']
    (out/'population_recovery.md').write_text(('\n'.join(lines)+'\n').replace('<10','<'+str(args.low_threshold)).replace('ниже 10','ниже '+str(args.low_threshold)));(out/'summary.json').write_text(json.dumps(dict(low_threshold=args.low_threshold,summary=summary,checked_population_rows=checks),indent=2));print(json.dumps(summary,indent=2));print('Population checkpoints verified:',checks)

if __name__=='__main__':main()
