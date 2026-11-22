import pathlib, json, ast, math, statistics as st
REPO = pathlib.Path(__file__).resolve().parents[2]
R = pathlib.Path.home() / 'Desktop/research'
B = REPO / '.ai/pipeline/report-build'
worlds = json.loads((B / 'data_audit.json').read_text())['worlds']
surv = json.loads((B / 'survival_ep500.json').read_text())['statuses']
tree = ast.parse((REPO / 'scripts/pipeline/rebuild_research_reports.py').read_text())
defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('betacf', 'ibeta', 'tc')]
scope = {'math': math}
exec(compile(ast.Module(body=defs, type_ignores=[]), 'quantiles', 'exec'), scope)
tc = scope['tc']
stages = [('1', 'Первые 15 seeds', 1, None), ('2', '+30 seeds для всех', 2, None), ('3', '+15 seeds для всех', 3, None), ('4', '+10 seeds для всех', 4, None), ('5a', '+30 seeds: clons и mendel', 5, 'without_new_non_linear'), ('5b', 'Те же 30 seeds: добавлен non_linear', 5, None), ('6', '+100 seeds для всех, survival 500', 6, None), ('7', '+50 seeds: mendel и non_linear, probe 2000', 7, None), ('8', '+50 seeds для всех, survival 500', 8, None), ('9', '+50 seeds для всех, survival 500', 9, None)]

def batchnum(w):
    return int(w['batch'].split('-')[0][5:])

def included(w, sp, limit, mode):
    return batchnum(w) <= limit and (not (mode and sp == 'non_linear' and (batchnum(w) == 5)))
lines = ['# История добавления seeds и изменения CI', '', 'Восстановлено по сохранённым мирам, reproducibility.md и архиву соответствий партий после объединения папок. Корзина не требуется.', '', '**Это ретроспективный пересчёт накопленных данных единым нынешним методом.** Строки не означают, что после каждой партии мы действительно публиковали именно такой CI. В раннем чате менялись пересечения (сначала общие выжившие всех трёх видов, позже каждой пары), горизонты и метод расчёта выживаемости. Поэтому опубликованные тогда числа могли отличаться.', '', 'Этап 5 разделён: сначала новые 30 seeds запускались для clons/mendel, затем на этих же seeds был добавлен non_linear. Партии 2–4 заказывались в том числе заранее в очередь; их строки ниже — восстановленные промежуточные срезы.', '', '## Добавление данных', '', '| Этап | Добавление | Накоплено probe: C/M/N | Накоплено всех миров: C/M/N |', '| --- | --- | --- | --- |']
selected = []
for (label, desc, limit, mode) in stages:
    ws = {sp: {s: w for (s, w) in vv.items() if included(w, sp, limit, mode)} for (sp, vv) in worlds.items()}
    selected.append((label, ws))
    counts = [len(ws[s]) for s in ('clons', 'mendel', 'non_linear')]
    pc = [sum((w['kind'] == 'probe' for w in ws[s].values())) for s in ('clons', 'mendel', 'non_linear')]
    lines.append('| ' + label + ' | ' + desc + ' | ' + ' / '.join(map(str, pc)) + ' | ' + ' / '.join(map(str, counts)) + ' |')
lines += ['', 'C=clons, M=mendel, N=non_linear. Это числа основных миров, а не отдельных изолированных probe-агентов. Один seed, запущенный у трёх видов, даёт три основных мира.', '', '## Probe: горизонт 2000 эпизодов', '', 'Метрика и отбор совпадают с final_results.md: общий seed, оба вида дожили до 2000; среднее по последним трём снимкам ≤40000 шагов. SD выборочное; SEM=SD/√n; MoE=t₀.₉₇₅,ₙ₋₁×SEM. Ни 5000-й, ни 500-й эпизод не подменяет 2000-й.', '']
result = {'probe': {}, 'survival': {}}
for (a, b) in [('mendel', 'clons'), ('non_linear', 'clons'), ('non_linear', 'mendel')]:
    key = a + '-' + b
    result['probe'][key] = []
    lines += ['### ' + a + ' − ' + b, '', '| Этап | Общих seeds n | Среднее | SD | SEM | MoE 95% | 95% CI | d>0 | d>30 | d>60 |', '| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |']
    for (label, ws) in selected:
        common = ws[a].keys() & ws[b].keys()
        diffs = [ws[a][s]['probe'] - ws[b][s]['probe'] for s in common if ws[a][s]['probe'] is not None and ws[b][s]['probe'] is not None]
        n = len(diffs)
        assert n >= 2
        m = st.mean(diffs)
        sd = st.stdev(diffs)
        se = sd / math.sqrt(n)
        moe = tc(n - 1) * se
        counts = [sum((d > t for d in diffs)) for t in (0, 30, 60)]
        lines.append(f'| {label} | {n} | {m:+.3f} | {sd:.3f} | {se:.3f} | ±{moe:.3f} | [{m - moe:+.3f}; {m + moe:+.3f}] | ' + ' | '.join((f'{v}/{n}' for v in counts)) + ' |')
        result['probe'][key].append(dict(stage=label, n=n, mean=m, sd=sd, sem=se, moe=moe, ci=[m - moe, m + moe]))
    lines.append('')
lines += ['## Выживаемость: единый горизонт 500 эпизодов', '', 'Использованы и отдельные survival-партии, и состояние длинных probe-миров на шаге 10000. Для каждой пары берутся общие seeds; dᵢ=I(A выжил)−I(B выжил), SEM=SD(dᵢ)/√n, MoE=1.959964×SEM. Все разности и погрешности ниже — процентные пункты.', '']
for (a, b) in [('clons', 'mendel'), ('clons', 'non_linear'), ('non_linear', 'mendel')]:
    key = a + '-' + b
    result['survival'][key] = []
    lines += ['### ' + a + ' − ' + b, '', '| Этап | Общих seeds n | Выжило A | Выжило B | Разность, пп | SEM, пп | MoE 95%, пп | 95% CI, пп |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for (label, ws) in selected:
        common = ws[a].keys() & ws[b].keys()
        n = len(common)
        aa = sum((surv[a][s] for s in common))
        bb = sum((surv[b][s] for s in common))
        d = [int(surv[a][s]) - int(surv[b][s]) for s in common]
        m = 100 * st.mean(d)
        se = 100 * st.stdev(d) / math.sqrt(n)
        moe = 1.959963984540054 * se
        lines.append(f'| {label} | {n} | {aa}/{n} ({100 * aa / n:.1f}%) | {bb}/{n} ({100 * bb / n:.1f}%) | {m:+.3f} | {se:.3f} | ±{moe:.3f} | [{m - moe:+.3f}; {m + moe:+.3f}] |')
        result['survival'][key].append(dict(stage=label, n=n, mean=m, sem=se, moe=moe, ci=[m - moe, m + moe]))
    lines.append('')
lines += ['## Как читать историю', '', 'Изменение числа запущенных seeds и числа общих выживших — разные вещи. Новые 50 запусков каждого вида не обязательно добавляют 50 наблюдений в probe-сравнение. Партии survival без probe не меняют probe-CI.', '', 'Все интервалы точечные, без поправки на множественные сравнения и последовательное добавление данных.', '', 'Источники: archive/layout_migration.json; archive/reports/latest/data_audit.json; archive/reports/latest/survival_ep500.json; файл reproducibility.md проекта.']
(REPO / '.ai/pipeline/seed_history.md').write_text('\n'.join(lines) + '\n')
(REPO / '.ai/pipeline/seed_history.json').write_text(json.dumps(result, indent=2))
print('History reconstructed: 10 stages, 3 probe pairs, 3 survival pairs')
final = json.loads((REPO / '.ai/pipeline/independent_audit_result.json').read_text())
for (key, series) in result['probe'].items():
    v = series[-1]
    e = final['probe'][key]
    assert v['n'] == e['n'] and abs(v['mean'] - e['mean']) < 1e-09 and (max((abs(x - y) for (x, y) in zip(v['ci'], e['ci']))) < 1e-06)
for (key, series) in result['survival'].items():
    v = series[-1]
    e = final['survival'][key]
    assert v['n'] == e['n'] and abs(v['mean'] - e['mean_pp']) < 1e-09
print('Final rows match the independent audit')
