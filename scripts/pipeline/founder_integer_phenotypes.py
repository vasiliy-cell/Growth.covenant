import pathlib,json,csv,collections
import pyarrow.dataset as ds
R=pathlib.Path.home()/'Desktop/research';O=pathlib.Path(__file__).resolve().parents[2]/'.ai/pipeline/founder_integer_phenotypes';O.mkdir(exist_ok=True)
worlds=list(csv.DictReader((R/'founder_genes/founder_world_features.csv').open()));counts=collections.Counter();den=collections.Counter();raw=[];presence=[]
for w in worlds:
 sp=w['species'];seed=w['seed'];dead=int(w['extinct']);p=next((R/'logs').glob('*/'+sp+'/seed-'+seed+'/run.json'));t=ds.dataset(str(p.parent/'events/births'),format='parquet').to_table(columns=['agent_id','phen_hidden_layers','phen_hidden_size'],filter=ds.field('step')==0).to_pylist();assert len(t)==20
 values=[]
 for a in t:
  row=dict(species=sp,seed=seed,extinct=dead,agent_id=a['agent_id'])
  for gene in ('hidden_layers','hidden_size'):
   v=float(a['phen_'+gene]);assert v.is_integer();v=int(v);counts[sp,gene,dead,v]+=1;den[sp,gene,dead]+=1;row[gene]=v
  raw.append(row);values.append(row['hidden_layers'])
 presence.append(dict(species=sp,seed=seed,extinct=dead,founders_1_layer=values.count(1),founders_2_layers=values.count(2),founders_3_plus_layers=sum(v>=3 for v in values)))
for name,rows in [('founder_phenotypes.csv',raw),('world_layer_composition.csv',presence)]:
 with (O/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=['# Целочисленные фенотипы основателей','', 'Реальные записанные phen_hidden_layers и phen_hidden_size каждого из 20 основателей, без усреднения и без повторного округления генотипа. Вымершие — до ep500. Проценты агентов описательные; агенты одного мира не являются независимыми повторностями.',''];freq=[]
for sp in ('clons','mendel','non_linear'):
 for gene in ('hidden_layers','hidden_size'):
  lines+=['## '+sp+' — '+gene,'','| Целый фенотип | Основателей вымерших | Основателей выживших |','| --- | ---: | ---: |']
  vals=sorted({k[3] for k in counts if k[:2]==(sp,gene)})
  for v in vals:
   a=counts[sp,gene,1,v];b=counts[sp,gene,0,v];na=den[sp,gene,1];nb=den[sp,gene,0];lines.append(f'| {v} | {a}/{na} ({100*a/na:.2f}%) | {b}/{nb} ({100*b/nb:.2f}%) |');freq.append(dict(species=sp,gene=gene,value=v,dead_founders=a,alive_founders=b,dead_percent=100*a/na,alive_percent=100*b/nb))
   if gene=='hidden_layers':print(sp,v,a,b,round(100*a/na,2),round(100*b/nb,2))
  lines.append('')
(O/'integer_phenotype_distributions.md').write_text('\n'.join(lines)+'\n')
with (O/'frequencies.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(freq[0]));w.writeheader();w.writerows(freq)
assert len(raw)==20000
