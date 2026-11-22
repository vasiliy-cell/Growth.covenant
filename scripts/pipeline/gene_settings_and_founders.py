#!/usr/bin/env python3
"""Document actual experiment gene settings and founder phenotypes."""
import argparse,json,csv
from pathlib import Path
import numpy as np
import pyarrow.dataset as ds

def fmt(x):
 x=float(x)
 if abs(x)<1e-12:x=0.
 return f'{x:.6g}'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--research-root',type=Path,default=Path.home()/'Desktop/research');ap.add_argument('--output',type=Path,default=Path('gene_tables'));args=ap.parse_args();root=args.research_root;out=args.output;out.mkdir(exist_ok=True,parents=True);species=('clons','mendel','non_linear');values={s:{} for s in species};ref=None;counts={s:0 for s in species};raw=[]
 for p in sorted((root/'logs').glob('*/*/seed-*/run.json')):
  h=json.loads(p.read_text());g=h['sessions'][0]['config']['genome'];sp=h['species']
  if ref is None:ref=g
  assert g['genes']==ref['genes'] and set(g['evolve'])==set(ref['evolve'])
  cols=['agent_id']+['phen_'+gene for gene in ref['genes']];rows=ds.dataset(str(p.parent/'events/births'),format='parquet').to_table(columns=cols,filter=ds.field('step')==0).to_pylist();assert len(rows)==20;counts[sp]+=1
  for r in rows:
   row=dict(species=sp,seed=h['sessions'][0]['seed'],agent_id=r['agent_id'])
   for gene in ref['genes']:
    v=float(r['phen_'+gene]);assert np.isfinite(v)
    if ref['genes'][gene]['type']=='int':assert v.is_integer()
    values[sp].setdefault(gene,[]).append(v);row[gene]=v
   raw.append(row)
 assert counts=={'clons':300,'mendel':350,'non_linear':350} and len(raw)==20000
 roles={'alpha':'Размах смешивания родителей у non_linear','sigma':'Вероятность мутации гена','learning_rate':'Скорость обучения Adam','max_norm':'Порог clipping нормы градиента','gamma':'Дисконтирование будущей награды','target_update_freq':'Период обновления target network','hidden_size':'Нейронов в скрытом слое','hidden_layers':'Число скрытых слоёв','buffer_size':'Ёмкость replay buffer','batch_size':'Размер обучающего batch','min_buffer_size':'Порог начала обучения из buffer','epsilon':'Начальная вероятность случайного действия','epsilon_decay':'Множитель затухания epsilon','epsilon_min':'Нижняя граница epsilon','curiosity_beta':'Начальный вес curiosity','curiosity_decay':'Множитель затухания curiosity'}
 lines=['# Гены: исходные настройки и разброс основателей','', 'Источник настроек — run.json фактически выполненных экспериментов bad-baseline с эволюцией. У всех 1000 миров проверено совпадение параметров генов и списка эволюции. Фактические распределения ниже рассчитаны по 20 000 основателям (рождения на шаге 0), включая основателей вымерших миров. Потомки и изменения генов в течение жизни сюда не входят.','', '## Исходные настройки','','| Ген | Назначение | Тип фенотипа | Центр μ | Разброс σ в конфиге | Варьируется / эволюционирует |','| --- | --- | --- | ---: | ---: | --- |']
 for gene,spec in ref['genes'].items():
  active=gene in ref['evolve'];lines.append(f'| `{gene}` | {roles[gene]} | {spec["type"]} | {fmt(spec["mean"])} | {fmt(spec["scale"])} | {"Да" if active else "Нет: фиксирован на μ"} |')
 lines+=['', '**Что значит σ:** это стандартное отклонение нормального распределения при генерации исходного генотипа, а не жёсткие границы диапазона и не величина мутации. Затем применяются предусмотренные кодом ограничения и преобразование в фенотип. Поэтому фактические SD и диапазоны ниже могут отличаться от σ.','', '**Замороженные гены:** alpha, sigma и min_buffer_size. Их scale указан в конфиге, но при выключенной эволюции этого гена случайный результат не используется — значение берётся равным μ.','', '**Целочисленные гены:** округление и ограничения применяются при формировании фенотипа; отдельный агент имеет целое значение. Дробное среднее по множеству агентов в таблице не означает дробное число слоёв у агента. У mendel два аллеля каждого гена; в таблицах ниже учитывается ровно один записанный выраженный фенотип на основателя, а не среднее аллелей.','']
 stats=[]
 for sp in species:
  lines += [f'## Фактические фенотипы основателей: {sp}', '',f'{counts[sp]} миров, {counts[sp]*20} основателей. SD — выборочное стандартное отклонение по всем основателям этого механизма, а не SD средних миров. Все значения до округления отображения взяты из phen_* основного лога рождения.','', '| Ген | Среднее | SD | Q25 | Медиана | Q75 | Минимум | Максимум |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
  for gene in ref['genes']:
   v=np.array(values[sp][gene]);q=np.quantile(v,[.25,.5,.75]);r=dict(species=sp,gene=gene,n=len(v),mean=float(v.mean()),sd=float(v.std(ddof=1)),q25=float(q[0]),median=float(q[1]),q75=float(q[2]),minimum=float(v.min()),maximum=float(v.max()));stats.append(r)
   lines.append('| `'+gene+'` | '+' | '.join(fmt(r[k]) for k in ('mean','sd','q25','median','q75','minimum','maximum'))+' |')
  lines.append('')
 lines += ['Q25 и Q75 — границы, ниже которых находятся соответственно 25% и 75% наблюдений. Между ними лежат средние 50% наблюдений; это не доверительный интервал.','', '## Отдельный baseline без эволюции','', 'В новом baseline на 10 seeds × 3 механизма заморожены все 16 генов: genome.evolve=[]. Значения основателей и потомков фиксированы на μ из первой таблицы; случайного разброса значений генов нет, несмотря на ненулевые scale в настройках. Этот baseline не смешан с фактическими распределениями 20 000 основателей выше.','', 'Примечание: epsilon и curiosity могут затухать в ходе жизни по правилам обучения; таблица описывает исходные наследуемые настройки, а не их поздние значения поведения.']
 (out/'genes_and_founders.md').write_text('\n'.join(lines)+'\n')
 for name,rows in [('founder_gene_statistics.csv',stats),('founder_phenotypes.csv',raw)]:
  with (out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print('Verified 16 genes, consistent settings in 1000 worlds and 20000 founder phenotypes')

if __name__=='__main__':main()
