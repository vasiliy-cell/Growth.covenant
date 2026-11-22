#!/usr/bin/env python3
"""Standalone CI check + next-round decision for the overnight loop.
No Claude/model calls - pure python, invoked by overnight_loop.sh.

Reads all clean probe/survival data under ~/Desktop/research/batchN-*,
computes the two CI fronts (A: mendel-non_linear probe diff,
B: survival-rate, worst of the 3 pairs), decides which needs more data,
and prints a decision the bash loop can act on.

Usage:
  overnight_ci_check.py decide      -> prints "PROBE" or "SURVIVAL" (which front gets next round) or "DONE"
  overnight_ci_check.py seeds N     -> prints N new seeds (one per line), excluding every seed ever used
  overnight_ci_check.py report      -> writes the final summary markdown and prints its path
"""
import sys, os, glob, re, math, json
import statistics as st

RESEARCH = os.path.expanduser("~/Desktop/research")
REPO = "/Users/macbookairm4/projects/Growth.covenant"
sys.path.insert(0, REPO)
import pyarrow.compute as pc
from src.persistence.log_reader import RunLogReader

PROBE_BATCH_DIRS = {  # subdir -> species folder layout
    "batch1-clons": None, "batch1-mendel": None, "batch1-non_linear": None,  # flat (seed-* directly)
    "batch2-30": "sp", "batch3-extra15": "sp", "batch4-extra10": "sp", "batch5-third30": "sp",
    "batch7-mn": "sp",
}
SURVIVAL_BATCH_DIRS = {
    "batch6-survival100": "sp", "batch8-survival50": "sp",
}

def real_seed(seed_dir):
    rj = os.path.join(seed_dir, "run.json")
    if not os.path.exists(rj):
        return None
    m = re.search(r'"seed": (\d+)', open(rj).read())
    return m.group(1) if m else None

def iter_species_dirs(batch_dirs, species):
    for b, layout in batch_dirs.items():
        base = os.path.join(RESEARCH, b)
        if layout == "sp":
            base = os.path.join(base, species)
        elif species == "clons" and "clons" not in b:
            continue
        elif species == "mendel" and "mendel" not in b:
            continue
        elif species == "non_linear" and "non_linear" not in b:
            continue
        if not os.path.isdir(base):
            continue
        for d in glob.glob(base + "/seed-*"):
            s = os.path.basename(d).replace("seed-", "")
            if real_seed(d) == s:
                yield s, d

def probe_survivors(species):
    out = {}
    for s, d in iter_species_dirs(PROBE_BATCH_DIRS, species):
        if len(glob.glob(d + "/probe/step_*")) >= 18:
            out[s] = d
    return out

def survival_pop_survivors(species):
    out = {}
    for s, d in iter_species_dirs(SURVIVAL_BATCH_DIRS, species):
        try:
            r = RunLogReader(d)
            pop = r.episode_population()
            if pop.num_rows == 0:
                continue
            last_agents = pop.column("agents")[-1].as_py()
            out[s] = last_agents > 0
        except Exception:
            pass
    return out

def all_survival_status(species):
    """True survivors from BOTH probe batches (they have survival info too, via final pop) and survival-only batches."""
    out = {}
    for s, d in iter_species_dirs(PROBE_BATCH_DIRS, species):
        try:
            r = RunLogReader(d)
            pop = r.episode_population()
            if pop.num_rows == 0:
                continue
            out[s] = pop.column("agents")[-1].as_py() > 0
        except Exception:
            pass
    out.update(survival_pop_survivors(species))
    return out

def last3_ep2000(sd):
    snaps = sorted(int(os.path.basename(x).split("_")[1]) for x in glob.glob(sd + "/probe/step_*"))
    snaps = [s for s in snaps if s <= 40000]
    last3 = snaps[-3:]
    vals = []
    for step in last3:
        aws = [a for a in glob.glob(f"{sd}/probe/step_{step:09d}/2026*") if os.path.exists(a + "/run.json")]
        v = [pc.sum(RunLogReader(a).steps().column("env_reward")).as_py() for a in aws]
        if v:
            vals.append(st.mean(v))
    return st.mean(vals) if vals else None

def t_stat(diffs):
    n = len(diffs)
    if n < 3:
        return 0.0, None, None, n
    mean = st.mean(diffs)
    sd = st.stdev(diffs)
    sem = sd / math.sqrt(n)
    if sem == 0:
        return float("inf"), mean, 0.0, n
    return abs(mean) / sem, mean, sem, n

def probe_front():
    M = probe_survivors("mendel")
    N = probe_survivors("non_linear")
    common = sorted(set(M) & set(N))
    diffs = []
    for s in common:
        vm = last3_ep2000(M[s])
        vn = last3_ep2000(N[s])
        if vm is not None and vn is not None:
            diffs.append(vm - vn)
    t, mean, sem, n = t_stat(diffs)
    return dict(n=n, mean=mean, sem=sem, t=t, diffs=diffs)

def survival_front():
    C = all_survival_status("clons")
    M = all_survival_status("mendel")
    N = all_survival_status("non_linear")
    results = {}
    for name, A, B in [("clons_mendel", C, M), ("clons_non_linear", C, N), ("mendel_non_linear", M, N)]:
        common = sorted(set(A) & set(B))
        a_vals = [1 if A[s] else 0 for s in common]
        b_vals = [1 if B[s] else 0 for s in common]
        n = len(common)
        if n == 0:
            results[name] = dict(n=0, diff=None, se=None, t=0.0)
            continue
        pa = sum(a_vals) / n
        pb = sum(b_vals) / n
        diff = pa - pb
        se = math.sqrt(pa * (1 - pa) / n + pb * (1 - pb) / n) if n > 0 else None
        t = abs(diff) / se if se and se > 0 else 0.0
        results[name] = dict(n=n, diff=diff * 100, se=(se * 100 if se else None), t=t, pa=pa * 100, pb=pb * 100)
    return results

def worst_survival_t(results):
    ts = [v["t"] for v in results.values() if v["n"] > 0]
    return min(ts) if ts else 0.0

def all_used_seeds():
    used = set()
    for f in glob.glob(REPO + "/scripts/pipeline/seeds*.sh"):
        for m in re.finditer(r'\b(\d{6,10})\b', open(f).read()):
            used.add(int(m.group(1)))
    led = REPO + "/.ai/pipeline/overnight_used_seeds.txt"
    if os.path.exists(led):
        for line in open(led):
            line = line.strip()
            if line:
                used.add(int(line))
    return used

def gen_seeds(n):
    import numpy as np
    used = all_used_seeds()
    rng = np.random.default_rng()  # time-seeded, fine: uniqueness enforced by exclusion set
    out = []
    while len(out) < n:
        v = int(rng.integers(1, 2**31 - 1))
        if v not in used and v not in out:
            out.append(v)
    led = REPO + "/.ai/pipeline/overnight_used_seeds.txt"
    os.makedirs(os.path.dirname(led), exist_ok=True)
    with open(led, "a") as f:
        for s in out:
            f.write(str(s) + "\n")
    return out

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "decide"
    if cmd == "seeds":
        n = int(sys.argv[2])
        for s in gen_seeds(n):
            print(s)
        return
    pf = probe_front()
    sf = survival_front()
    sf_t = worst_survival_t(sf)
    if cmd == "decide":
        # thresholds from the conversation: probe resolved if CI excludes 0 (t>1.96) OR sem<15/2.0 (moe<15 roughly t needs mean/sem large enough... use moe directly)
        probe_resolved = False
        if pf["n"] >= 3 and pf["sem"]:
            moe = 1.96 * pf["sem"]
            probe_resolved = (abs(pf["mean"]) > moe) or (moe < 15)
        survival_all_resolved = True
        for v in sf.values():
            if v["n"] < 3 or v["se"] is None:
                survival_all_resolved = False
                continue
            moe = 1.96 * v["se"]
            width_ok = (moe * 2) < 10  # total CI width < 10pp -> negligible, resolved as "no diff"
            clearly_nonzero = abs(v["diff"]) > moe
            if clearly_nonzero:
                # need HIGH precision once direction is clear: require moe < 3pp
                if moe >= 3:
                    survival_all_resolved = False
            elif not width_ok:
                survival_all_resolved = False
        if probe_resolved and survival_all_resolved:
            print("DONE")
        elif probe_resolved and not survival_all_resolved:
            print("SURVIVAL")
        elif survival_all_resolved and not probe_resolved:
            print("PROBE")
        else:
            # both unresolved: compare t-stats, weaker (smaller t) gets the round
            print("SURVIVAL" if sf_t <= pf["t"] else "PROBE")
    elif cmd == "report":
        lines = []
        lines.append("# Overnight loop - final report")
        lines.append("")
        lines.append(f"## mendel-non_linear probe diff (n={pf['n']})")
        if pf["n"] >= 3:
            moe = 1.96 * pf["sem"]
            lines.append(f"d={pf['mean']:.1f}, SEM={pf['sem']:.1f}, 95% CI=[{pf['mean']-moe:+.1f}, {pf['mean']+moe:+.1f}], t={pf['t']:.2f}")
        lines.append("")
        lines.append("## Survival rate (percentage points)")
        for name, v in sf.items():
            if v["n"] == 0:
                lines.append(f"{name}: no common seeds")
                continue
            moe = 1.96 * v["se"] if v["se"] else 0
            lines.append(f"{name}: n={v['n']}, diff={v['diff']:+.1f}pp, 95% CI=[{v['diff']-moe:+.1f}, {v['diff']+moe:+.1f}], t={v['t']:.2f}")
        text = "\n".join(lines)
        path = os.path.join(RESEARCH, "overnight_final_report.md")
        with open(path, "w") as f:
            f.write(text + "\n")
        print(path)
    else:
        print("unknown command", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
