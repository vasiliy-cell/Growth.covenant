import json,pathlib,math,statistics as st
import pyarrow.dataset as ds
r=json.load(open(str(pathlib.Path(__file__).resolve().parents[2]/'.ai/pipeline/report-build/data_audit.json')))['worlds'];out={}
for sp,worlds in r.items():
 out[sp]={}
 for s,w in worlds.items():
  p=pathlib.Path(w['path'])/'episodes/population'
  rows=ds.dataset([str(f) for f in sorted(p.glob('*.parquet'))],format='parquet').to_table(columns=['session','step_end','agents']).to_pylist()
  if w['header_last_step']<10000:
   assert w['final_agents']==0;alive=False
  else:
   eligible=[x for x in rows if x['step_end']<=10000];last=max(eligible,key=lambda x:(x['session'],x['step_end']))
   assert last['step_end']==10000,(sp,s,last)
   alive=last['agents']>0
  out[sp][s]=alive
print('AT EP500', {sp:(sum(v.values()),len(v)) for sp,v in out.items()})
pairs={}
for a,b in [('clons','mendel'),('clons','non_linear'),('mendel','non_linear')]:
 common=out[a].keys()&out[b].keys();n=len(common);d=[int(out[a][s])-int(out[b][s]) for s in common];mean=100*st.mean(d);sem=100*st.stdev(d)/math.sqrt(n)
 # Large-sample paired Wald CI, explicit method in report.
 moe=1.959963984540054*sem
 pairs[a+'-'+b]={'n':n,'a_survivors':sum(out[a][s] for s in common),'b_survivors':sum(out[b][s] for s in common),'mean_pp':mean,'sem_pp':sem,'moe_pp':moe,'ci_pp':[mean-moe,mean+moe],'a_only':sum(out[a][s] and not out[b][s] for s in common),'b_only':sum(out[b][s] and not out[a][s] for s in common)}
 print(a,b,pairs[a+'-'+b])
(pathlib.Path(__file__).resolve().parents[2]/'.ai/pipeline/report-build/survival_ep500.json').write_text(json.dumps({'statuses':out,'pairs':pairs},indent=2))
