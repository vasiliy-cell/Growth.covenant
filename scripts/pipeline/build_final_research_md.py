#!/usr/bin/env python3
"""Build the owner's final pairwise results document from verified local logs."""
import datetime
import json
import math
from pathlib import Path
import statistics as st

REPO=Path(__file__).resolve().parents[2]
BUILD=REPO/'.ai/pipeline/report-build'
OUTPUT=REPO/'.ai/pipeline/final_results.md'

def main():
    status=json.loads((REPO/'.ai/pipeline/batch9_mac_status.json').read_text())
    assert status['state']=='complete' and status['checksum']=='matched'
    audit=json.loads((BUILD/'data_audit.json').read_text());assert not audit['issues']
    worlds=audit['worlds']
    assert sum(map(len,worlds.values()))==1000
    results=json.loads((BUILD/'results.json').read_text())
    survival=json.loads((BUILD/'survival_ep500.json').read_text())
    lines=['# Итоговые результаты: партии 1–9', '',
           'Данные: 1000 завершённых миров. По одному наблюдению на seed и вид размножения. Проверены соответствие seed имени папки, отсутствие повторов и завершённость забегов. Логи текущего сервера сверены по контрольным суммам.', '',
           '## 1. Probe: сравнение только до 2000 эпизодов', '',
           'В каждой паре используются все общие seeds, у которых оба мира дожили до 2000 эпизодов и имеют probe-измерения. Выживание третьего вида не требуется. Партии без probe не включены. Даже если основной забег продолжался до 3000 или 5000 эпизодов, используются только снимки не позже шага 40000 (2000 эпизодов × 20 шагов).', '',
           'Метрика мира: в каждом из последних трёх доступных probe-снимков до этого предела суммируется env_reward за изолированный прогон каждого выбранного агента, затем берётся среднее по агентам и среднее по трём снимкам. Это сумма внешней награды в probe, а не награда основной популяции. Разность всегда равна первому виду минус второй.', '',
           'Статистика считается по парным разностям dᵢ: SD — выборочное стандартное отклонение, SEM=SD/√n, MoE(95%)=t₀.₉₇₅,ₙ₋₁×SEM, CI=mean(dᵢ)±MoE. Для расчётов использованы неокруглённые значения; в таблицах три знака после запятой.', '']
    for index,(a,b,key,sign) in enumerate([
        ('mendel','clons','mendel-clons',1),
        ('non_linear','clons','non_linear-clons',1),
        ('non_linear','mendel','mendel-non_linear',-1)],1):
        common=sorted(set(worlds[a])&set(worlds[b]),key=int)
        common=[s for s in common if worlds[a][s]['probe'] is not None and worlds[b][s]['probe'] is not None]
        r=results['probe'][key];assert len(common)==r['n']
        diffs=[];av=[];bv=[]
        lines += [f'### 1.{index}. {a} − {b}', '',
                  f'**Все совпадающие seeds: n={len(common)} ({2*len(common)} миров).**', '',
                  f'| seed | Партия | {a} | {b} | {a} − {b} |',
                  '| --- | --- | ---: | ---: | ---: |']
        for seed in common:
            wa,wb=worlds[a][seed],worlds[b][seed]
            assert all(s['step']<=40000 for w in (wa,wb) for s in w['snapshots'])
            assert len(wa['snapshots'])==len(wb['snapshots'])==3
            va,vb=wa['probe'],wb['probe'];d=va-vb
            av.append(va);bv.append(vb);diffs.append(d)
            batch='batch1' if wa['batch'].startswith('batch1-') else wa['batch']
            lines.append(f'| {seed} | {batch} | {va:.3f} | {vb:.3f} | {d:+.3f} |')
        mean=st.mean(diffs);sd=st.stdev(diffs);sem=sd/math.sqrt(len(diffs))
        assert math.isclose(mean,sign*r['mean'],abs_tol=1e-10)
        assert math.isclose(sd,r['sd'],abs_tol=1e-10)
        lo,hi=(r['ci'] if sign==1 else [-r['ci'][1],-r['ci'][0]])
        lines.append(f'| **Среднее** | **{len(common)} seeds** | **{st.mean(av):.3f}** | **{st.mean(bv):.3f}** | **{mean:+.3f}** |')
        lines += ['', '| Метрика | Значение |', '| --- | ---: |',
                  f'| n, общих seeds | {len(common)} |', f'| Среднее разности d̄ | {mean:+.3f} |',
                  f'| SD | {sd:.3f} |',f'| SEM | {sem:.3f} |',
                  f'| MoE (95%) | ±{r["moe"]:.3f} |',f'| 95% CI | [{lo:+.3f}; {hi:+.3f}] |']
        for threshold in (0,30,60):
            count=sum(d>threshold for d in diffs)
            lines.append(f'| Разность > {threshold} | {count}/{len(diffs)} ({100*count/len(diffs):.1f}%) |')
        lines.append('')
    lines += ['## 2. Выживаемость до 500 эпизодов', '',
              'Единый горизонт для всех партий: популяция основной симуляции > 0 на шаге 10000 (500 эпизодов × 20 шагов). Если мир вымер раньше, он учитывается как невыживший. Для длинных забегов берётся состояние именно на шаге 10000; их финальная популяция на 2000/3000/5000 эпизодах здесь не используется. Поэтому разные длительности забегов в этом разделе не смешиваются.', '',
              '| Вид | Выжило | Всего миров | Выживаемость |', '| --- | ---: | ---: | ---: |']
    for sp in ('clons','mendel','non_linear'):
        v=survival['statuses'][sp];n=len(v);alive=sum(v.values())
        lines.append(f'| {sp} | {alive} | {n} | {100*alive/n:.3f}% |')
    lines += ['', '### Попарные разности выживаемости', '',
              'Используются только общие seeds каждой пары. Для сравнений с clons их 300, поскольку дополнительные 50 seeds партии 7 запускались только для mendel и non_linear. Общие проценты в предыдущей таблице относятся ко всем мирам каждого вида, поэтому их прямое вычитание может отличаться от парных разностей ниже.', '',
              'Парная оценка: dᵢ=I(выжил первый вид)−I(выжил второй вид), SEM=SD(dᵢ)/√n, MoE=1.959964×SEM, 95% CI=d̄±MoE. Разности и погрешности выражены в процентных пунктах (пп).', '',
              '| Пара: первый − второй | Общих seeds | Выжило: первый | Выжило: второй | Разность, пп | SEM, пп | MoE (95%), пп | 95% CI, пп |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for a,b,key,sign in [('clons','mendel','clons-mendel',1),('clons','non_linear','clons-non_linear',1),('non_linear','mendel','mendel-non_linear',-1)]:
        r=survival['pairs'][key];n=r['n'];aa=r['a_survivors'] if sign==1 else r['b_survivors'];bb=r['b_survivors'] if sign==1 else r['a_survivors'];m=sign*r['mean_pp'];lo,hi=r['ci_pp'] if sign==1 else [-r['ci_pp'][1],-r['ci_pp'][0]]
        lines.append(f'| {a} − {b} | {n} | {aa}/{n} ({100*aa/n:.3f}%) | {bb}/{n} ({100*bb/n:.3f}%) | {m:+.3f} | {r["sem_pp"]:.3f} | ±{r["moe_pp"]:.3f} | [{lo:+.3f}; {hi:+.3f}] |')
    lines += ['', '## Примечания', '',
              'Все 95% интервалы — обычные точечные интервалы, без поправки на несколько сравнений и последовательный просмотр результатов. Probe-оценки относятся к мирам, дожившим до 2000 эпизодов в обоих видах пары; вымершие миры включены в раздел выживаемости, но не подменяются нулевой probe-наградой.', '',
              'Сырые логи: `logs/`. Аудит с выбранными probe-снимками: `archive/reports/latest/data_audit.json`. Исходные результаты выживаемости по seeds: `archive/reports/latest/survival_ep500.json`.', '']
    OUTPUT.write_text('\n'.join(lines))
    print(OUTPUT)
    print('Pairwise rows:',[results['probe'][k]['n'] for k in ('mendel-clons','non_linear-clons','mendel-non_linear')])
    print('Survival worlds:',sum(map(len,survival['statuses'].values())))

if __name__=='__main__':main()
