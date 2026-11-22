#!/usr/bin/env python3
"""Exploratory founder-only gene associations with extinction by episode 500."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,json,csv,math
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds

def ranks(x):
 o=np.argsort(x,kind='stable');r=np.empty(len(x),float);i=0
 while i<len(x):
  j=i+1
  while j<len(x) and x[o[j]]==x[o[i]]:j+=1
  r[o[i:j]]=(i+j-1)/2;i=j
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('founder_genes'));ap.add_argument('--permutations',type=int,default=2000);args=ap.parse_args();root=args.research_root;out=args.output;out.mkdir(exist_ok=True,parents=True)
 migration=json.loads((root/'archive/layout_migration.json').read_text());batch={x['world_id']:x['batch'].split('-')[0] for x in migration};records=[];constant={};rng=np.random.default_rng(20261114)
 for p in sorted((root/'logs').glob('*/*/seed-*/run.json')):
  h=json.loads(p.read_text());session=h['sessions'][0];assert len(h['sessions'])==1 and session.get('finished_at');d=p.parent
  t=ds.dataset(str(d/'events/births'),format='parquet');columns=['step','agent_id','genotype_json']+[c for c in t.schema.names if c.startswith('phen_')]
  founders=t.to_table(columns=columns,filter=ds.field('step')==0).to_pylist();assert len(founders)==20 and len({x['agent_id'] for x in founders})==20
  deaths=ds.dataset(str(d/'events/deaths'),format='parquet').to_table(columns=['step'],filter=ds.field('step')<=10000).num_rows if list((d/'events/deaths').glob('*.parquet')) else 0
  births=t.to_table(columns=['step'],filter=ds.field('step')<=10000).num_rows
  extinct=(births-deaths)==0;assert not extinct or session['to_step']<=10000
  features={};genomes=[json.loads(f['genotype_json']) for f in founders]
  for gene in sorted(genomes[0]):
   vals=[];dom=[]
   for g in genomes:
    value=g[gene]
    if isinstance(value,list):vals.extend(float(a[0]) for a in value);dom.extend(a[1]=='A' for a in value)
    else:vals.append(float(value))
   features[gene+'|genotype_mean']=float(np.mean(vals));features[gene+'|genotype_sd']=float(np.std(vals,ddof=1));features[gene+'|genotype_min']=min(vals);features[gene+'|genotype_max']=max(vals)
   col='phen_'+gene
   if col in founders[0]:
    v=[float(f[col]) for f in founders];features[gene+'|phenotype_mean']=float(np.mean(v));features[gene+'|phenotype_sd']=float(np.std(v,ddof=1))
   if dom:features[gene+'|dominant_allele_fraction']=float(np.mean(dom))
  records.append(dict(species=h['species'],seed=session['seed'],world_id=h['world_id'],batch=batch[h['world_id']],extinct=int(extinct),extinction_step=session['to_step'] if extinct else None,features=features))
 assert len(records)==1000 and len({(r['species'],r['seed']) for r in records})==1000
 allresults=[];counts={}
 for sp in ('clons','mendel','non_linear'):
  rr=[r for r in records if r['species']==sp];counts[sp]={'total':len(rr),'extinct':sum(r['extinct'] for r in rr)}
  names=sorted(rr[0]['features']);X=np.array([[r['features'][k] for k in names] for r in rr]);spread=np.ptp(X,axis=0);valid=(spread>1e-10)&np.array([k.split("|")[0] not in ("alpha","sigma","min_buffer_size") for k in names]);constant[sp]=[k for k,v in zip(names,valid) if not v];X=X[:,valid];names=[k for k,v in zip(names,valid) if v]
  for mode in ('extinct_vs_survived','time_among_extinct'):
   mask=np.ones(len(rr),bool) if mode=='extinct_vs_survived' else np.array([bool(r['extinct']) for r in rr]);rs=[r for r,m in zip(rr,mask) if m];A=X[mask].copy();y=np.array([r['extinct'] if mode=='extinct_vs_survived' else r['extinction_step'] for r in rs],float)
   if mode=='time_among_extinct':A=np.column_stack([ranks(A[:,j]) for j in range(A.shape[1])]);y=ranks(y)
   # Residualize by original batch, then permute outcomes only within batch.
   groups=[np.array([i for i,r in enumerate(rs) if r['batch']==b]) for b in sorted({r['batch'] for r in rs})]
   for ix in groups:A[ix]-=A[ix].mean(axis=0);y[ix]-=y[ix].mean()
   norm=np.sqrt((A*A).sum(axis=0)*(y*y).sum());ok=norm>1e-10;A=A[:,ok];nn=[k for k,v in zip(names,ok) if v];norm=norm[ok];observed=np.einsum('i,ij->j',y,A,optimize=False)/norm
   perm=np.empty((args.permutations,len(y)))
   for i in range(args.permutations):
    perm[i]=y
    for ix in groups:perm[i,ix]=rng.permutation(y[ix])
   scores=np.abs(np.einsum('ij,jk->ik',perm,A,optimize=False)/norm);assert np.isfinite(scores).all() and np.isfinite(observed).all();maxima=scores.max(axis=1)
   for j,name in enumerate(nn):
    threshold=abs(observed[j])-1e-12;praw=(1+np.sum(scores[:,j]>=threshold))/(args.permutations+1);pmax=(1+np.sum(maxima>=threshold))/(args.permutations+1)
    original=np.array([r['features'][name] for r in rr]);dead=np.array([bool(r['extinct']) for r in rr]);sd=original.std(ddof=1);difference=original[dead].mean()-original[~dead].mean()
    allresults.append(dict(species=sp,analysis=mode,feature=name,n=len(rs),batch_adjusted_association=float(observed[j]),mean_extinct=float(original[dead].mean()),mean_survived=float(original[~dead].mean()),difference_in_world_sd=float(difference/sd),p_raw=float(praw),p_maxT=float(pmax),p_adjusted_all_six=min(1.,float(pmax)*6)))
  print('Analyzed',sp,counts[sp],flush=True)
 fields=['species','seed','world_id','batch','extinct','extinction_step'];features=sorted(set(k for r in records for k in r['features']))
 with (out/'founder_world_features.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields+features);w.writeheader()
  for r in records:w.writerow({**{k:r[k] for k in fields},**r['features']})
 allresults.sort(key=lambda r:(r['p_adjusted_all_six'],r['p_raw']))
 with (out/'all_associations.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(allresults[0]));w.writeheader();w.writerows(allresults)
 lines=['# Гены основателей и вымирание мира','', 'Только 20 основателей (births, step=0) каждого из 1000 миров и исход мира до 500 эпизодов. Признаки: среднее, SD, минимум, максимум значений генотипа основателей; среднее и SD их исходного фенотипа; у mendel также доля доминантных аллелей. Значения обоих аллелей mendel учитываются явно, а не смешиваются с одиночными генами других механизмов. Анализ проводится отдельно по механизмам. Потомки, возраст, награды и последующая эволюция генов не анализировались.','', 'Два вопроса: (1) связь исходных генов с вымиранием к ep500; (2) связь с временем смерти среди вымерших. Для второго используется ранговая связь: отрицательное значение означает связь с более ранним вымиранием. Для первого положительное значение означает большие значения признака у вымерших миров.','', 'Единица анализа — мир, а не отдельный основатель. Учитываются исходные партии: признаки и исход центрируются внутри партии, исход переставляется только между мирами той же партии. 2000 перестановок. p_maxT учитывает поиск по всем признакам одного механизма и вопроса; затем p_adjusted_all_six дополнительно умножается на 6 (3 механизма × 2 вопроса). Уровень 0.05 применяется к последнему столбцу. Это разведочный анализ, не причинный вывод.','', '## Число миров','','| Вид | Всего | Вымерли до ep500 |','| --- | ---: | ---: |']
 for sp,v in counts.items():lines.append(f'| {sp} | {v["total"]} | {v["extinct"]} |')
 significant=[r for r in allresults if r['p_adjusted_all_six']<=.05];lines+=['',f'Признаков, прошедших общую поправку: **{len(significant)}**.','']
 for mode,label in [('extinct_vs_survived','Вымирание к ep500'),('time_among_extinct','Время вымирания среди вымерших')]:
  lines+=['## '+label,'','Показаны пять наиболее выраженных кандидатов на механизм; остальные — в CSV.','', '| Вид | Признак | Связь с учётом партии | Среднее у вымерших | Среднее у выживших | p без поправки | p с общей поправкой |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
  for sp in counts:
   subset=sorted([r for r in allresults if r['species']==sp and r['analysis']==mode],key=lambda r:r['p_raw'])[:5]
   for r in subset:lines.append(f'| {sp} | {r["feature"]} | {r["batch_adjusted_association"]:+.3f} | {r["mean_extinct"]:.5g} | {r["mean_survived"]:.5g} | {r["p_raw"]:.4f} | {r["p_adjusted_all_six"]:.4f} |')
 lines+=['','genotype_mean/sd/min/max относятся ко всем 20 основателям (40 аллелям для mendel). phenotype_mean/sd — к выраженным исходным значениям генов тех же основателей. Для таблицы времени смерти столбцы средних относятся к полным группам вымерших/выживших и служат контекстом; проверка там использует только вымершие миры.','', 'alpha, sigma, min_buffer_size и другие постоянные признаки исключаются из проверки корреляций: без вариации оценивать их связь с исходом нельзя. Все исключённые признаки перечислены в constant_features.json.']
 (out/'founder_genes_extinction.md').write_text('\n'.join(lines)+'\n');(out/'constant_features.json').write_text(json.dumps(constant,indent=2));(out/'summary.json').write_text(json.dumps(dict(counts=counts,significant=significant,top=allresults[:12]),indent=2));print('Significant after correction:',len(significant),flush=True)

if __name__=='__main__':main()
