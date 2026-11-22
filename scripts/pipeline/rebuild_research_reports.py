import pathlib,json,math,statistics as st,itertools,sys
import pyarrow.dataset as ds
import pyarrow.compute as pc
R=pathlib.Path.home()/'Desktop/research/logs'
O=pathlib.Path(__file__).resolve().parents[2]/'.ai/pipeline/report-build';O.mkdir(exist_ok=True)
SPECIES=('clons','mendel','non_linear')
BATCHES=[('batch1-'+s,{s:None},'probe') for s in SPECIES]+[(b,{s:s for s in SPECIES},'probe') for b in ('batch2-30','batch3-extra15','batch4-extra10','batch5-third30')]+[('batch6-survival100',{s:s for s in SPECIES},'survival'),('batch7-mn',{s:s for s in ('mendel','non_linear')},'probe'),('batch8-survival50',{s:s for s in SPECIES},'survival'),('batch9-survival50',{s:s for s in SPECIES},'survival')]
records={s:{} for s in SPECIES};issues=[]
def table(p,columns):
 files=sorted(p.glob('*.parquet'))
 if not files:raise ValueError('No parquet: '+str(p))
 return ds.dataset([str(f) for f in files],format='parquet').to_table(columns=columns)
for batch,layout,kind in BATCHES:
 for species,sub in layout.items():
  base=R/batch
  if sub:base/=sub
  migration=pathlib.Path.home()/'Desktop/research/archive/layout_migration.json'
  paths=sorted(base.glob('seed-*')) if base.exists() else [pathlib.Path(x['new']) for x in json.loads(migration.read_text()) if x['batch']==batch and x['species']==species]
  for d in paths:
   try:
    j=json.loads((d/'run.json').read_text()); seed=int(d.name[5:]);sess=j['sessions']
    if any(s['seed']!=seed for s in sess):raise ValueError('seed/name mismatch')
    if j['species']!=species:raise ValueError('species/folder mismatch')
    if seed in records[species]:raise ValueError('duplicate seed for species')
    if not all(s.get('finished_at') for s in sess):raise ValueError('unfinished session')
    pop=table(d/'episodes/population',['session','step_end','agents'])
    rows=pop.to_pylist(); last=max(rows,key=lambda x:(x['session'],x['step_end']))
    maxstep=max(s['to_step'] for s in sess);target=40000 if kind=='probe' else 10000
    if last['agents']>0 and maxstep<target:raise ValueError('live world ended before requested horizon')
    rec={'batch':batch,'kind':kind,'path':str(d),'world_id':j['world_id'],'seed':seed,'species':species,'last_step':last['step_end'],'header_last_step':maxstep,'final_agents':last['agents'],'survived':last['agents']>0,'probe':None,'snapshots':[]}
    if kind=='probe' and maxstep>=40000 and last['agents']>0:
     snaps=sorted(p for p in (d/'probe').glob('step_*') if int(p.name[5:])<=40000)
     if len(snaps)<3:raise ValueError('survivor missing three snapshots')
     vals=[]
     for snap in snaps[-3:]:
      worlds=sorted(p.parent for p in snap.glob('*/run.json'))
      if not worlds:raise ValueError('empty probe snapshot')
      av=[]
      for w in worlds:
       aj=json.loads((w/'run.json').read_text())
       if not all(s.get('finished_at') for s in aj['sessions']):raise ValueError('unfinished isolated agent probe')
       t=table(w/'steps',['env_reward']);v=pc.sum(t['env_reward']).as_py()
       if v is None or not math.isfinite(v):raise ValueError('invalid reward')
       av.append(float(v))
      vals.append(st.mean(av));rec['snapshots'].append({'step':int(snap.name[5:]),'agents':len(av),'agent_rewards':av,'mean_reward':st.mean(av)})
     rec['probe']=st.mean(vals)
     rec['snapshot_count']=len(snaps)
    records[species][seed]=rec
   except Exception as e:issues.append({'path':str(d),'error':str(e)})
print('World counts:',{s:len(v) for s,v in records.items()},flush=True)
print('Probe counts:',{s:sum(r['probe'] is not None for r in v.values()) for s,v in records.items()},flush=True)
(O/'data_audit.json').write_text(json.dumps({'issues':issues,'worlds':records},ensure_ascii=False,indent=2))
if issues:print(json.dumps(issues,ensure_ascii=False,indent=2));raise SystemExit('Audit failed; reports not written')
# Student t two-sided 95% quantile, via regularized incomplete beta.
def betacf(a,b,x):
 qab=a+b;qap=a+1;qam=a-1;c=1.;d=1-qab*x/qap
 if abs(d)<1e-300:d=1e-300
 d=1/d;h=d
 for m in range(1,300):
  aa=m*(b-m)*x/((qam+2*m)*(a+2*m));d=1+aa*d;c=1+aa/c
  if abs(d)<1e-300:d=1e-300
  if abs(c)<1e-300:c=1e-300
  d=1/d;h*=d*c
  aa=-(a+m)*(qab+m)*x/((a+2*m)*(qap+2*m));d=1+aa*d;c=1+aa/c
  if abs(d)<1e-300:d=1e-300
  if abs(c)<1e-300:c=1e-300
  d=1/d;delta=d*c;h*=delta
  if abs(delta-1)<3e-14:return h
 raise ValueError('beta did not converge')
def ibeta(a,b,x):
 if x<=0:return 0.
 if x>=1:return 1.
 bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
 return bt*betacf(a,b,x)/a if x<(a+1)/(a+b+2) else 1-bt*betacf(b,a,1-x)/b

def tc(df):
 lo,hi=0.,100.
 for _ in range(90):
  mid=(lo+hi)/2;p=1-.5*ibeta(df/2,.5,df/(df+mid*mid))
  if p<.975:lo=mid
  else:hi=mid
 return (lo+hi)/2
assert abs(tc(1)-12.706204736)<1e-7
assert abs(tc(30)-2.042272456)<1e-7
pairs=[('mendel','clons'),('non_linear','clons'),('mendel','non_linear')]
summary=['# Probe-статистика: episodes = 2000','', 'Bad-baseline (gamma=0.5, hidden_size=40). Партии 1–5 и 7. Один seed учитывается один раз в каждой паре. Включены миры, дожившие до 2000 эпизодов в обоих видах пары, независимо от третьего вида.','', 'Метрика мира: для каждого из последних трёх probe-снимков не позже шага 40000 суммируется env_reward каждого изолированного агента; затем берётся среднее по агентам и по трём снимкам. Разность: первый вид минус второй. SD выборочное; SEM=SD/√n; MoE=t₀.₉₇₅,ₙ₋₁×SEM.','']
results={}
for a,b in pairs:
 common=sorted(s for s in records[a].keys()&records[b].keys() if records[a][s]['probe'] is not None and records[b][s]['probe'] is not None)
 diffs=[records[a][s]['probe']-records[b][s]['probe'] for s in common];n=len(diffs)
 mean=st.mean(diffs);sd=st.stdev(diffs);sem=sd/math.sqrt(n);moe=tc(n-1)*sem
 result={'n':n,'mean':mean,'sd':sd,'sem':sem,'moe':moe,'ci':[mean-moe,mean+moe],'counts':{str(k):sum(d>k for d in diffs) for k in (0,30,60)}};results[a+'-'+b]=result
 section=[f'## {a} − {b} (n={n})','','| Метрика | Значение |','| --- | ---: |',f'| Среднее (d̄) | {mean:+.1f} |',f'| SD | {sd:.1f} |',f'| SEM | {sem:.1f} |',f'| MoE (95%) | ±{moe:.1f} |',f'| 95% CI | [{mean-moe:+.1f}, {mean+moe:+.1f}] |','','| Условие | Количество | Доля |','| --- | ---: | ---: |']
 for k in (0,30,60):
  count=result['counts'][str(k)];section.append(f'| {a} − {b} > {k} | {count}/{n} | {100*count/n:.1f}% |')
 summary.extend(section+[''])
 details=[f'# {a} − {b}: probe до 2000 эпизодов','']+section+['','| seed | Партия | '+a+' | '+b+' | Разность |','| --- | --- | ---: | ---: | ---: |']
 for s,d in zip(common,diffs):details.append(f'| {s} | {records[a][s]["batch"]} | {records[a][s]["probe"]:.3f} | {records[b][s]["probe"]:.3f} | {d:+.3f} |')
 (O/f'probe_{a}_vs_{b}.md').write_text('\n'.join(details)+'\n')
 print(a,b,result,flush=True)
(O/'probe_statistics_summary.md').write_text('\n'.join(summary)+'\n')
lines=['# Выживаемость: все завершённые партии 1–9','', 'Критерий: число агентов в последней строке основной популяции > 0. Probe-миры оцениваются в конце 2000 эпизодов, survival-партии — в конце 500. Партия 1 могла быть длиннее: её фактический конец указан в аудите. Сводная доля объединяет разные горизонты; это не вероятность выживания до единого срока.','', '| Партия | Горизонт, эпизоды | clons | mendel | non_linear |','| --- | ---: | ---: | ---: | ---: |']
for name in ['batch1','batch2-30','batch3-extra15','batch4-extra10','batch5-third30','batch6-survival100','batch7-mn','batch8-survival50','batch9-survival50']:
 row=[name,'500' if name in ('batch6-survival100','batch8-survival50','batch9-survival50') else ('2000–5000 (фактический конец)' if name=='batch1' else '2000')]
 for sp in SPECIES:
  rs=[r for r in records[sp].values() if r['batch'].startswith('batch1-') if name=='batch1'] if name=='batch1' else [r for r in records[sp].values() if r['batch']==name]
  row.append(f'{sum(r["survived"] for r in rs)}/{len(rs)}' if rs else '—')
 lines.append('| '+' | '.join(row)+' |')
lines+=['','## Общая сводка','','| Вид | Выжило | Всего | Доля |','| --- | ---: | ---: | ---: |']
for sp in SPECIES:
 rs=list(records[sp].values());alive=sum(r['survived'] for r in rs);lines.append(f'| {sp} | {alive} | {len(rs)} | {100*alive/len(rs):.1f}% |')
lines+=['','## Попарные разности на общих seeds','','Каждый seed представлен обоими видами. Сохранён прежний метод из чата: нормальный интервал разности двух долей (непарная формула), SE=√[pA(1−pA)/n+pB(1−pB)/n], MoE=1.96×SE. Этот метод не учитывает зависимость результатов на одинаковых seeds. Значения в процентных пунктах.','', '| Пара (A − B) | Общих seeds | Выжило A | Выжило B | Разность, пп | SEM, пп | MoE, пп | 95% CI, пп |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
survival={}
for a,b in [('clons','mendel'),('clons','non_linear'),('mendel','non_linear')]:
 common=sorted(records[a].keys()&records[b].keys());diffs=[int(records[a][s]['survived'])-int(records[b][s]['survived']) for s in common];n=len(diffs);m=100*st.mean(diffs);pa=sum(records[a][s]['survived'] for s in common)/n;pb=sum(records[b][s]['survived'] for s in common)/n;se=100*math.sqrt(pa*(1-pa)/n+pb*(1-pb)/n);moe=1.96*se
 aa=sum(records[a][s]['survived'] for s in common);bb=sum(records[b][s]['survived'] for s in common)
 lines.append(f'| {a} − {b} | {n} | {aa}/{n} | {bb}/{n} | {m:+.1f} | {se:.1f} | ±{moe:.1f} | [{m-moe:+.1f}, {m+moe:+.1f}] |')
 survival[a+'-'+b]={'n':n,'mean_pp':m,'sem_pp':se,'moe_pp':moe,'ci_pp':[m-moe,m+moe],'a_survivors':aa,'b_survivors':bb}
lines+=['','## Все миры','','| Вид | seed | Партия | Последний шаг | Финальная популяция | Выжил |','| --- | --- | --- | ---: | ---: | --- |']
for sp in SPECIES:
 for s,r in sorted(records[sp].items()):lines.append(f'| {sp} | {s} | {r["batch"]} | {r["last_step"]} | {r["final_agents"]} | {"да" if r["survived"] else "нет"} |')
(O/'survival_rate_summary.md').write_text('\n'.join(lines)+'\n')
report=['# Результаты партий 1–9','','Новых ночных раундов ovr не было. Включены завершённые партии 7–9.','', '## Probe (2000 эпизодов)','','| Пара | n | Среднее | 95% CI |','| --- | ---: | ---: | --- |']
for k,v in results.items():report.append(f'| {k} | {v["n"]} | {v["mean"]:+.1f} | [{v["ci"][0]:+.1f}, {v["ci"][1]:+.1f}] |')
report+=['','## Выживаемость (смешанные горизонты; подробности в сводке)','','| Вид | Выжило / всего | Доля |','| --- | ---: | ---: |']
for sp in SPECIES:
 rs=list(records[sp].values());alive=sum(r['survived'] for r in rs);report.append(f'| {sp} | {alive}/{len(rs)} | {100*alive/len(rs):.1f}% |')
report+=['','[Полная probe-статистика](probe_statistics_summary.md) · [Выживаемость и список миров](survival_rate_summary.md)','','95% CI probe рассчитаны через t-распределение. Сырые значения, пути и выбранные снимки: [data_audit.json](data_audit.json).']
(O/'overnight_final_report.md').write_text('\n'.join(report)+'\n')
(O/'results.json').write_text(json.dumps({'probe':results,'survival':survival},indent=2))
print('REPORTS READY',O,flush=True)
