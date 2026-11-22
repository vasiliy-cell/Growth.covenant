#!/usr/bin/env python3
"""Six single-threaded baseline worlds, preserving an adopted running world."""
import datetime,fcntl,json,os,signal,subprocess,time
from pathlib import Path
from run_local_frozen_baseline import REPO,STATE,thermal_reader,check_frozen

def main():
 os.chdir(REPO);lock=(STATE/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 plan=json.loads((STATE/'plan.json').read_text());status=json.loads((STATE/'status.json').read_text());thermal=thermal_reader();active=[];completed=status['completed'];done={(r['species'],r['seed']) for r in completed};adopt=json.loads((STATE/'adopt.json').read_text());paused=True;worked=0.;cooldown=0.
 def save():
  status.update(state='running',parallel=6,threads=1,active=[{k:v for k,v in x.items() if k!='proc'} for x in active],completed=completed,thermal_state=thermal(),updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat());p=STATE/'status.json.tmp';p.write_text(json.dumps(status,indent=2));p.replace(STATE/'status.json')
 def alive(job):
  if job.get('proc') is not None:return job['proc'].poll() is None
  try:os.kill(job['pid'],0);return True
  except ProcessLookupError:return False
 def validate(job):
  candidates=[]
  for p in (Path(plan['log_root'])/job['species']).glob('*/run.json'):
   h=json.loads(p.read_text())
   if h['sessions'][0]['seed']==job['seed']:candidates.append(p.parent)
  assert len(candidates)==1;world=candidates[0];n=check_frozen(world,plan['config'])
  import pyarrow.dataset as ds
  pop=ds.dataset(str(world/'episodes/population'),format='parquet').to_table(columns=['step_end','agents']).to_pylist();last=max(pop,key=lambda r:r['step_end']);assert last['step_end']==20000 or last['agents']==0
  import torch
  for snap in (world/'probe/snapshots').glob('step_*.pt'):
   record=torch.load(snap,map_location='cpu',weights_only=False);folder=world/'probe'/snap.stem;expected={a['agent_id'] for a in record['agents']};actual={p.parent.name for p in folder.glob('*/run.json')};assert actual==expected
   for p in folder.glob('*/run.json'):
    ss=json.loads(p.read_text())['sessions'];assert all(s.get('finished_at') and s['to_step']==400 for s in ss)
  return dict(species=job['species'],seed=job['seed'],exit=0,world=str(world),validated_births=n,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 if adopt:
  job=dict(adopt,proc=None)
  if alive(job):active.append(job)
  elif (job['species'],job['seed']) not in done:
   completed.append(validate(job));done.add((job['species'],job['seed']))
 pending=[(sp,seed) for sp in plan['species'] for seed in plan['seeds'] if (sp,seed) not in done and (not adopt or (sp,seed)!=(adopt['species'],adopt['seed']))]
 subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 last=time.monotonic();lastphase=None
 while active or pending:
  now=time.monotonic()
  if not paused:worked+=now-last
  last=now;heat=thermal()
  for job in list(active):
   if not alive(job):
    proc=job.get('proc')
    if proc is not None and proc.returncode!=0:raise RuntimeError(str(job['species'])+' '+str(job['seed'])+' failed')
    result=validate(job);completed.append(result);done.add((job['species'],job['seed']));active.remove(job);print('WORLD COMPLETE',json.dumps(result),flush=True)
  if not paused and (worked>=plan['work_seconds'] or heat>0):
   for job in active:
    try:os.killpg(job['pid'],signal.SIGSTOP)
    except ProcessLookupError:pass
   paused=True;cooldown=now+plan['rest_seconds']
  if paused and now>=cooldown and heat==0:
   for job in active:
    try:os.killpg(job['pid'],signal.SIGCONT)
    except ProcessLookupError:pass
   paused=False;worked=0.;last=now
  while not paused and pending and len(active)<6:
   sp,seed=pending.pop(0);cmd=[str(REPO/'.venv/bin/python3'),'src/run.py','--episodes','1000','--seed',str(seed),'--agents','20','--species',sp,'--label',f'bad-frozen1000-{sp}-seed{seed}','--series',sp,'--resume','','--no-pin','--probe']
   for key,value in plan['config'].items():cmd+=['--set',key+'='+json.dumps(value,separators=(',',':'))]
   env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONPATH='.',MPLCONFIGDIR='/tmp/growth-matplotlib-cache')
   with (STATE/f'{sp}_{seed}.log').open('w') as log:proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
   active.append(dict(species=sp,seed=seed,pid=proc.pid,proc=proc));print('START',sp,seed,proc.pid,flush=True)
  status['phase']=('thermal_pause' if heat>0 else 'cooldown') if paused else 'working';status['current']=None;status['active_seconds_since_rest']=worked
  if status['phase']!=lastphase:print('PHASE',status['phase'],'thermal',heat,flush=True);lastphase=status['phase']
  save();time.sleep(5)
 status.update(state='complete',phase='complete',active=[],current=None,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat());p=STATE/'status.json';p.write_text(json.dumps(status,indent=2));(Path(plan['archive_root'])/'completed.json').write_text(json.dumps(status,indent=2));print('ALL 30 WORLDS COMPLETE',flush=True)

if __name__=='__main__':
 try:main()
 except Exception as e:
  try:
   previous=json.loads((STATE/'status.json').read_text())
   for job in previous.get('active',[]):
    try:os.killpg(job['pid'],signal.SIGSTOP)
    except ProcessLookupError:pass
   previous.update(state='failed',phase='paused_after_error',error=repr(e));(STATE/'status.json').write_text(json.dumps(previous,indent=2))
  except Exception:pass
  (STATE/'parallel_failure.json').write_text(json.dumps({'error':repr(e)},indent=2));raise
