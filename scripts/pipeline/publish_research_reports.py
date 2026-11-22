#!/usr/bin/env python3
"""Publish the one requested table; keep audits and other reports in archive."""
import argparse
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, default=Path(__file__).resolve().parents[2]/'.ai/pipeline/report-build')
    args = parser.parse_args()
    root = Path.home()/'Desktop/research'
    audit = json.loads((args.build/'data_audit.json').read_text())
    assert not audit['issues']
    worlds = audit['worlds']
    common = sorted(set(worlds['mendel']) & set(worlds['non_linear']), key=int)
    common = [s for s in common if worlds['mendel'][s]['probe'] is not None and worlds['non_linear'][s]['probe'] is not None]
    result = json.loads((args.build/'results.json').read_text())['probe']['mendel-non_linear']
    assert len(common) == result['n']
    lines = ['# non_linear − mendel: все общие миры, probe до 2000 эпизодов', '',
             f'{len(common)} общих seeds ({2*len(common)} миров). В обоих видах мир дожил до 2000 эпизодов. Метрика: средняя env_reward изолированных агентов, усреднённая по последним трём probe-снимкам не позже шага 40000. Разность = non_linear − mendel.', '',
             '| seed | Партия | non_linear | mendel | non_linear − mendel |',
             '| --- | --- | ---: | ---: | ---: |']
    for seed in common:
        n = worlds['non_linear'][seed]
        m = worlds['mendel'][seed]
        assert n['batch'] == m['batch'] or (n['batch'].startswith('batch1-') and m['batch'].startswith('batch1-'))
        batch = 'batch1' if n['batch'].startswith('batch1-') else n['batch']
        lines.append(f'| {seed} | {batch} | {n["probe"]:.3f} | {m["probe"]:.3f} | {n["probe"]-m["probe"]:+.3f} |')
    nmean = sum(worlds['non_linear'][s]['probe'] for s in common)/len(common)
    mmean = sum(worlds['mendel'][s]['probe'] for s in common)/len(common)
    lines.append(f'| **Среднее** | **{len(common)} seeds** | **{nmean:.3f}** | **{mmean:.3f}** | **{-result["mean"]:+.3f}** |')
    lo, hi = -result['ci'][1], -result['ci'][0]
    lines += ['', f'SD разностей: {result["sd"]:.3f}; SEM: {result["sem"]:.3f}; MoE (95%): ±{result["moe"]:.3f}; **95% CI: [{lo:+.3f}; {hi:+.3f}]** (t-распределение).', '',
              'Партии только для выживаемости (500 эпизодов, без probe) в эту таблицу не входят. Интервал без поправки на множественные сравнения и последовательный просмотр.']
    path = root/'nonlinear-mendel.md'
    tmp = path.with_suffix('.md.tmp')
    tmp.write_text('\n'.join(lines)+'\n')
    tmp.replace(path)
    archive = root/'archive/reports/latest'
    archive.mkdir(parents=True, exist_ok=True)
    for f in args.build.iterdir():
        if f.is_file():
            shutil.copy2(f, archive/f.name)
    print(path, flush=True)


if __name__ == '__main__':
    main()
