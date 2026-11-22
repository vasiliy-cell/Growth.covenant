#!/usr/bin/env python3
"""Incremental Mac delivery, then checksum and regenerate reports for all batches."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[2]
DEST=Path.home()/'Desktop/research/logs/batch9-survival50'
STATE=REPO/'.ai/pipeline/batch9_mac_status.json'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
     '-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','-o','ControlMaster=auto',
     '-o','ControlPersist=600','-o','ControlPath=/tmp/research-pull-%C']
HOST='root@62.238.127.235'
REMOTE='''import json,pathlib
r=pathlib.Path('/root/Growth.covenant')
s=json.loads((r/'.ai/pipeline/batch9-survival50/status.json').read_text())
w=[]
for sp in ('clons','mendel','non_linear'):
 for p in sorted((r/'logs'/('batch9-survival50-'+sp)).glob('*/run.json')):
  try:
   j=json.loads(p.read_text());w.append(dict(species=sp,path=str(p.parent),seed=j['sessions'][0]['seed'],world_id=j['world_id']))
  except (ValueError,OSError):pass
print(json.dumps(dict(status=s,worlds=w)))
'''


def write_state(**kwargs):
    kwargs['updated_at']=time.time()
    tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(kwargs,indent=2));tmp.replace(STATE)


def sync(world):
    target=DEST/world['species']/('seed-'+str(world['seed']))
    target.mkdir(parents=True,exist_ok=True)
    marker=target/'.fetched_world_id'
    if marker.exists() and marker.read_text().strip()!=world['world_id']:
        raise RuntimeError('Different world already at '+str(target))
    cmd=['rsync','-rlt','--partial','--timeout=45','--exclude=*.tmp','-e',' '.join(SSH),
         HOST+':'+world['path']+'/',str(target)+'/']
    subprocess.run(cmd,check=True,timeout=600)
    j=json.loads((target/'run.json').read_text())
    if j['world_id']!=world['world_id'] or j['sessions'][0]['seed']!=world['seed']:
        raise RuntimeError('Transferred world identity mismatch: '+str(target))
    marker.write_text(world['world_id']+'\n')


def verify(worlds):
    # Compare directly with each seed folder. Avoid temporary directory
    # symlinks: receiver implementations differ in handling --keep-dirlinks.
    logs=[]
    for index,w in enumerate(worlds,1):
        target=DEST/w['species']/('seed-'+str(w['seed']))
        cmd=['rsync','-rcni','--timeout=90','--exclude=*.tmp','-e',' '.join(SSH),
             HOST+':'+w['path']+'/',str(target)+'/']
        proc=subprocess.run(cmd,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
        if proc.stdout.strip():
            raise RuntimeError('Checksum differences at '+str(target)+': '+proc.stdout[:2000])
        logs.append(w['species']+' seed-'+str(w['seed'])+': 0 differing files')
        if index % 25 == 0:
            print('Checksum verified',index,'/',len(worlds),flush=True)
            write_state(state='verifying',completed_simulations=150,worlds=len(worlds),verified_worlds=index)
    (REPO/'.ai/pipeline/batch9_checksum.txt').write_text('\n'.join(logs)+'\n')


def reports():
    for script in ('rebuild_research_reports.py','survival_common_horizon.py','format_survival_500.py','publish_research_reports.py'):
        subprocess.run([sys.executable,str(REPO/'scripts/pipeline'/script)],check=True)


def main():
    lock=(REPO/'.ai/pipeline/batch9_mac_sync.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        try:
            proc=subprocess.run(SSH+[HOST,'python3 -'],input=REMOTE,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=60)
            data=json.loads(proc.stdout);status=data['status'];worlds=data['worlds']
            done=len(status['results']);failed=[r for r in status['results'] if r['exit']!=0]
            write_state(state='syncing',completed_simulations=done,failed_simulations=len(failed),worlds=len(worlds))
            for w in worlds:sync(w)
            print(f'Synced {len(worlds)} worlds; completed {done}/150; errors {len(failed)}',flush=True)
            if status['state']=='complete':
                assert done==150 and len(worlds)==150 and not failed
                write_state(state='verifying',completed_simulations=150,worlds=150,verified_worlds=0)
                verify(worlds)
                reports()
                write_state(state='complete',completed_simulations=150,worlds=150,checksum='matched',reports='updated')
                print('BATCH9: ALL LOGS VERIFIED; ALL REPORTS UPDATED',flush=True)
                return
            if status['state']=='failed':
                write_state(state='server_failed',failed=failed)
                raise SystemExit('Server finished with errors; check console logs')
            write_state(state='waiting',completed_simulations=done,worlds=len(worlds))
        except (subprocess.SubprocessError,OSError,ValueError,RuntimeError,AssertionError) as e:
            print('Delivery retry:',repr(e),flush=True)
            write_state(state='retrying',error=repr(e))
        time.sleep(120)


if __name__=='__main__':
    main()
