import pathlib,json
O=pathlib.Path(__file__).resolve().parents[2]/'.ai/pipeline/report-build';j=json.loads((O/'survival_ep500.json').read_text());r=json.loads((O/'data_audit.json').read_text())['worlds'];lines=['# Выживаемость до одинаковых 500 эпизодов: партии 1–9','', 'Включены все завершённые миры. Выжил = основная популяция > 0 на шаге 10000 (500 эпизодов × 20 шагов). Мир, вымерший раньше, учитывается как невыживший. Probe-миры и survival-миры измерены на одном горизонте.','', '| Вид | Выжило | Всего | Доля |','| --- | ---: | ---: | ---: |']
for sp,v in j['statuses'].items():lines.append(f'| {sp} | {sum(v.values())} | {len(v)} | {100*sum(v.values())/len(v):.1f}% |')
lines+=['','## Попарное сравнение на одинаковых seeds','','В каждой паре берётся пересечение seeds. Поэтому в сравнениях с clons нет дополнительных 50 seeds партии 7.','', 'Парный нормальный 95% CI: dᵢ=I(A выжил)−I(B выжил), SE=SD(dᵢ)/√n, CI=mean(dᵢ)±1.959964×SE. Интервалы точечные, без поправки на множественные сравнения и последовательный просмотр данных.','', '| Пара (A − B) | n | Выжило A | Выжило B | Разница, пп | SE, пп | MoE, пп | 95% CI, пп |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
for pair,v in j['pairs'].items():lines.append(f'| {pair} | {v["n"]} | {v["a_survivors"]}/{v["n"]} | {v["b_survivors"]}/{v["n"]} | {v["mean_pp"]:+.1f} | {v["sem_pp"]:.1f} | ±{v["moe_pp"]:.1f} | [{v["ci_pp"][0]:+.1f}, {v["ci_pp"][1]:+.1f}] |')
lines+=['','## Несовпадающие исходы в паре','','| Пара | Только A выжил | Только B выжил |','| --- | ---: | ---: |']
for pair,v in j['pairs'].items():lines.append(f'| {pair} | {v["a_only"]} | {v["b_only"]} |')
lines+=['','## По партиям','','| Партия | clons | mendel | non_linear |','| --- | ---: | ---: | ---: |']
for batch in ['batch1','batch2-30','batch3-extra15','batch4-extra10','batch5-third30','batch6-survival100','batch7-mn','batch8-survival50','batch9-survival50']:
 row=[batch]
 for sp in ('clons','mendel','non_linear'):
  ss=[s for s,w in r[sp].items() if (w['batch'].startswith('batch1-') if batch=='batch1' else w['batch']==batch)]
  row.append(f'{sum(j["statuses"][sp][s] for s in ss)}/{len(ss)}' if ss else '—')
 lines.append('| '+' | '.join(row)+' |')
lines+=['','## Все миры','','| Вид | seed | Партия | Выжил до ep500 |','| --- | --- | --- | --- |']
for sp,statuses in j['statuses'].items():
 for s,v in sorted(statuses.items(),key=lambda x:int(x[0])):lines.append(f'| {sp} | {s} | {r[sp][s]["batch"]} | {"да" if v else "нет"} |')
(O/'survival_rate_ep500.md').write_text('\n'.join(lines)+'\n')
p=O/'overnight_final_report.md';s=p.read_text();start=s.index('## Выживаемость');end=s.index('[Полная probe-статистика]',start)
s=s[:start]+'## Выживаемость до 500 эпизодов\n\n| Пара | n | Разность, пп | 95% CI, пп (парный) |\n| --- | ---: | ---: | --- |\n'+'\n'.join(f'| {k} | {v["n"]} | {v["mean_pp"]:+.1f} | [{v["ci_pp"][0]:+.1f}, {v["ci_pp"][1]:+.1f}] |' for k,v in j['pairs'].items())+'\n\n[Сопоставимая выживаемость до ep500](survival_rate_ep500.md)\n\n'+s[end:]
s+='\nОбычные 95% CI без поправок на многократные проверки и несколько сравнений.\n';p.write_text(s)
p=O/'probe_statistics_summary.md';p.write_text(p.read_text()+'\nИнтервалы точечные, без поправки на множественные сравнения и последовательный просмотр данных.\n')
print('Formatted standardized survival report')
