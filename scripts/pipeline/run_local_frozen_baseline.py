#!/usr/bin/env python3
"""Thirty local frozen-gene bad-baseline worlds with thermal-aware duty cycling."""
import ctypes
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

REPO=Path(__file__).resolve().parents[2]
STATE=REPO/'.ai/pipeline/local_bad_baseline_frozen_1000'


def thermal_reader():
    ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    objc.objc_getClass.argtypes=[ctypes.c_char_p];objc.objc_getClass.restype=ctypes.c_void_p
    objc.sel_registerName.argtypes=[ctypes.c_char_p];objc.sel_registerName.restype=ctypes.c_void_p
    pointer=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
    integer=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
    info=pointer(objc.objc_getClass(b'NSProcessInfo'),objc.sel_registerName(b'processInfo'))
    selector=objc.sel_registerName(b'thermalState')
    return lambda:int(integer(info,selector))


def check_frozen(world,config):
    import pyarrow.dataset as ds
    header=json.loads((world/'run.json').read_text())
    assert header['sessions'][0]['config']['genome']['evolve']==[]
    means={k:v['mean'] for k,v in config['genome']['genes'].items()}
    rows=ds.dataset(str(world/'events/births'),format='parquet').to_table(columns=['genotype_json']).to_pylist()
    assert len(rows)>=20
    for row in rows:
        genotype=json.loads(row['genotype_json'])
        assert set(genotype)==set(means)
        for gene,value in genotype.items():
            values=[a[0] for a in value] if isinstance(value,list) else [value]
            assert all(float(v)==means[gene] for v in values),(str(world),gene,values,means[gene])
    assert header['sessions'][0].get('finished_at')
    return len(rows)


def main():
    os.chdir(REPO)
    lock=(STATE/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((STATE/'plan.json').read_text());status_path=STATE/'status.json'
    if status_path.exists():raise SystemExit('Already started: refusing a duplicate baseline run')
    thermal=thermal_reader();assert thermal() in (0,1,2,3)
    status=dict(state='running',started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                completed=[],current=None,phase='initializing',thermal_state=thermal(),parallel=1,
                threads=1,work_seconds=300,rest_seconds=120,probe=True)
    def save():
        status['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        temp=STATE/'status.json.tmp';temp.write_text(json.dumps(status,indent=2));temp.replace(status_path)
    save()
    archive=Path(plan['archive_root']);archive.mkdir(parents=True,exist_ok=True)
    (archive/'plan.json').write_text(json.dumps(plan,indent=2))
    subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    worked=0.;pause_until=0.;last_phase=None
    for species in plan['species']:
        for seed in plan['seeds']:
            cfg=plan['config'];label=f'bad-frozen1000-{species}-seed{seed}'
            cmd=[str(REPO/'.venv/bin/python3'),'src/run.py','--episodes','1000','--seed',str(seed),
                 '--agents','20','--species',species,'--label',label,'--series',species,
                 '--resume','','--no-pin','--probe']
            for key,value in cfg.items():cmd+=['--set',key+'='+json.dumps(value,separators=(',',':'))]
            env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                     VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONPATH='.',MPLCONFIGDIR='/tmp/growth-matplotlib-cache')
            status['current']=dict(species=species,seed=seed);save()
            console=STATE/f'{species}_{seed}.log'
            started=datetime.datetime.now(datetime.timezone.utc).isoformat()
            with console.open('w') as log:
                proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                status['current']['pid']=proc.pid;status['current']['command']=cmd
                paused=False;last=time.monotonic()
                try:
                    while proc.poll() is None:
                        now=time.monotonic()
                        if not paused:worked+=now-last
                        last=now;heat=thermal();status['thermal_state']=heat
                        if not paused and (heat>0 or worked>=plan['work_seconds']):
                            os.killpg(proc.pid,signal.SIGSTOP);paused=True;pause_until=now+plan['rest_seconds']
                        if paused and now>=pause_until and heat==0:
                            os.killpg(proc.pid,signal.SIGCONT);paused=False;worked=0.;last=now
                        status['phase']=('thermal_pause' if heat>0 else 'cooldown') if paused else 'working'
                        status['active_seconds_since_rest']=round(worked,1)
                        if status['phase']!=last_phase:
                            print(status['updated_at'],species,seed,status['phase'],'thermal',heat,flush=True);last_phase=status['phase']
                        save();time.sleep(5)
                except BaseException:
                    if proc.poll() is None:
                        if paused:os.killpg(proc.pid,signal.SIGCONT)
                        os.killpg(proc.pid,signal.SIGTERM)
                    raise
            if proc.returncode!=0:raise RuntimeError(f'{species} seed {seed} exited {proc.returncode}; see {console}')
            folder=Path(plan['log_root'])/species
            matches=[]
            for p in folder.glob('*/run.json'):
                h=json.loads(p.read_text())
                if h['sessions'][0]['seed']==seed:matches.append(p.parent)
            assert len(matches)==1
            births=check_frozen(matches[0],cfg)
            result=dict(species=species,seed=seed,exit=0,started_at=started,
                        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        world=str(matches[0]),validated_births=births)
            status['completed'].append(result);save();print('WORLD COMPLETE',json.dumps(result),flush=True)
    status.update(state='complete',phase='complete',current=None,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
    (archive/'completed.json').write_text(json.dumps(status,indent=2));print('ALL 30 FROZEN BASELINE WORLDS COMPLETE',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        p=STATE/'failure.json';p.write_text(json.dumps(dict(error=repr(exc),time=datetime.datetime.now().isoformat()),indent=2))
        raise
