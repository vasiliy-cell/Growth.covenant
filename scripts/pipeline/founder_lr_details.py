#!/usr/bin/env python3
"""Descriptive founder learning-rate distributions; worlds are independent units."""
import argparse,csv,json,math
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds

def pct(a,b):return f'{100*a/b:.1f}%' if b else '—'
def save(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('founder_lr_details'));args=ap.parse_args();out=args.output;out.mkdir(exist_ok=True,parents=True)
 source=list(csv.DictReader((args.research_root/'founder_genes/founder_world_features.csv').open()));worlds=[];agents=[]
 for r in source:
  sp=r['species'];seed=int(r['seed']);paths=list((args.research_root/'logs').glob(f'*/{sp}/seed-{seed}/run.json'));assert len(paths)==1;d=paths[0].parent
  t=ds.dataset(str(d/'events/births'),format='parquet').to_table(columns=['agent_id','phen_learning_rate','genotype_json'],filter=ds.field('step')==0).to_pylist();assert len(t)==20
  vals=[float(x['phen_learning_rate']) for x in t];dead=int(r['extinct']);assert math.isclose(np.mean(vals),float(r['learning_rate|phenotype_mean']),abs_tol=1e-12)
  w=dict(species=sp,seed=seed,extinct=dead,mean_lr=float(np.mean(vals)),sd_lr=float(np.std(vals,ddof=1)),founders_below_001=sum(x<.001 for x in vals),founders_below_0008=sum(x<.0008 for x in vals),founders_below_0005=sum(x<.0005 for x in vals));worlds.append(w)
  for x,v in zip(t,vals):
   g=json.loads(x['genotype_json'])['learning_rate'];alleles=[float(a[0]) for a in g] if isinstance(g,list) else [float(g)]
   agents.append(dict(species=sp,seed=seed,extinct=dead,agent_id=x['agent_id'],phenotype_lr=v,genotype_allele_mean=float(np.mean(alleles))))
 save(out/'world_lr.csv',worlds);save(out/'founder_lr.csv',agents)
 lines=['# Learning rate основателей: подробные распределения','', 'Все 1000 миров, 20 000 основателей. Исход — вымирание до 500 эпизодов; выжившие = живы к этому сроку. Анализируется только learning rate стартовых агентов, без потомков. Основная переменная — исходный фенотип learning rate: выраженное значение, реально использовавшееся агентом. Для mendel это не среднее двух аллелей; исходные аллели сохранены отдельно в CSV.','', 'Ориентир конфига — 0,001. Значение ниже ориентира не означает неисправность. Границы ниже — описательные диапазоны, а не найденные пороги причинного эффекта. Проценты агентов описывают состав основателей; статистическая единица остаётся миром. Дополнительных тестов значимости здесь нет.',''];summary={}
 for sp in ('clons','mendel','non_linear'):
  ww=[w for w in worlds if w['species']==sp];aa=[a for a in agents if a['species']==sp];dead=[w for w in ww if w['extinct']];alive=[w for w in ww if not w['extinct']];ad=[a for a in aa if a['extinct']];av=[a for a in aa if not a['extinct']]
  summary[sp]={'dead_worlds':len(dead),'alive_worlds':len(alive),'groups':{}}
  lines += [f'## {sp}', '',f'Вымерли: {len(dead)} миров / {len(ad)} основателей. Выжили: {len(alive)} миров / {len(av)} основателей.','', '### Распределение по отдельным основателям','','| Группа | Среднее | Q25 | Медиана | Q75 | Минимум | Максимум |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
  for label,arr in [('Вымершие',ad),('Выжившие',av)]:
   v=np.array([a['phenotype_lr'] for a in arr]);q=np.quantile(v,[.25,.5,.75]);lines.append(f'| {label} | {v.mean():.7f} | {q[0]:.7f} | {q[1]:.7f} | {q[2]:.7f} | {v.min():.7f} | {v.max():.7f} |')
  lines+=['','| Learning rate агента | Среди основателей вымерших | Среди основателей выживших |','| --- | ---: | ---: |']
  edges=[-float('inf'),.0005,.0008,.001,.0012,.0015,float('inf')];labels=['<0,0005','0,0005–<0,0008','0,0008–<0,001','0,001–<0,0012','0,0012–<0,0015','≥0,0015']
  for lo,hi,label in zip(edges,edges[1:],labels):
   a=sum(lo<=r['phenotype_lr']<hi for r in ad);b=sum(lo<=r['phenotype_lr']<hi for r in av);lines.append(f'| {label} | {a}/{len(ad)} ({pct(a,len(ad))}) | {b}/{len(av)} ({pct(b,len(av))}) |')
  lines+=['','### Сколько основателей с пониженным LR в одном мире','','Пониженный здесь означает строго <0,001.','', '| Основателей с LR<0,001 из 20 | Вымерших миров | Выживших миров | Доля вымерших среди миров этой строки |','| --- | ---: | ---: | ---: |']
  for lo,hi in [(0,0),(1,4),(5,9),(10,14),(15,19),(20,20)]:
   a=sum(lo<=w['founders_below_001']<=hi for w in dead);b=sum(lo<=w['founders_below_001']<=hi for w in alive);lines.append(f'| {lo}' + (f'–{hi}' if hi!=lo else '')+f' | {a} ({pct(a,len(dead))}) | {b} ({pct(b,len(alive))}) | {a}/{a+b} ({pct(a,a+b)}) |')
  lines+=['','### Частота похожего отклонения и сильного понижения','','| Условие мира | Среди вымерших | Среди выживших |','| --- | ---: | ---: |']
  for key,label,fn in [('mean_below_ref','Средний LR 20 основателей <0,001',lambda w:w['mean_lr']<.001),('mean_below_000978','Средний LR ≤0,000978 (около найденного среднего mendel у вымерших)',lambda w:w['mean_lr']<=.000978),('any_half','Хотя бы один основатель с LR<0,0005',lambda w:w['founders_below_0005']>=1),('at_least_5_half','Не менее 5 основателей с LR<0,0005',lambda w:w['founders_below_0005']>=5)]:
   a=sum(fn(w) for w in dead);b=sum(fn(w) for w in alive);summary[sp]['groups'][key]={'dead_n':a,'alive_n':b,'dead_percent':100*a/len(dead),'alive_percent':100*b/len(alive)};lines.append(f'| {label} | {a}/{len(dead)} ({pct(a,len(dead))}) | {b}/{len(alive)} ({pct(b,len(alive))}) |')
  lines+=['','Порог 0,000978 выбран после предыдущего анализа; его таблица описательная и не является независимым подтверждением.','', '### Вымирание в зависимости от среднего LR основателей','','| Средний LR мира | Вымерло | Выжило | Всего | Доля вымираний |','| --- | ---: | ---: | ---: | ---: |']
  edges=[-float('inf'),.0009,.00095,.001,.00105,.0011,float('inf')];labels=['<0,00090','0,00090–<0,00095','0,00095–<0,00100','0,00100–<0,00105','0,00105–<0,00110','≥0,00110']
  for lo,hi,label in zip(edges,edges[1:],labels):
   group=[w for w in ww if lo<=w['mean_lr']<hi];a=sum(w['extinct'] for w in group);lines.append(f'| {label} | {a} | {len(group)-a} | {len(group)} | {pct(a,len(group))} |')
  lines+=['','### Четверти распределения среднего LR мира','','Границы квартилей вычислены отдельно для каждого механизма по всем его мирам, независимо от исхода.','', '| Четверть | Диапазон среднего LR | Вымерло / всего | Доля вымираний |','| --- | --- | ---: | ---: |']
  v=np.array([w['mean_lr'] for w in ww]);q=np.quantile(v,[.25,.5,.75]);edges=[-float('inf'),*q,float('inf')]
  for i,(lo,hi) in enumerate(zip(edges,edges[1:]),1):
   group=[w for w in ww if lo<=w['mean_lr']<hi];a=sum(w['extinct'] for w in group);lines.append(f'| Q{i} | [{lo:.7f}; {hi:.7f}) | {a}/{len(group)} | {pct(a,len(group))} |');summary[sp]['groups']['quartile_'+str(i)]={'n':len(group),'dead':a,'percent':100*a/len(group)}
  lines.append('')
 (out/'founder_learning_rate_details.md').write_text('\n'.join(lines)+'\n');(out/'summary.json').write_text(json.dumps(summary,indent=2));assert len(worlds)==1000 and len(agents)==20000;print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
