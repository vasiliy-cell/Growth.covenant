#!/usr/bin/env python3
"""Incremental final archive and SHA-256 verification before server retirement."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import subprocess
import time

REPO=Path(__file__).resolve().parents[2]
ROOT=Path.home()/'Desktop/research'
ARCHIVE=ROOT/'archive/server-62.238.127.235'
STATE=REPO/'.ai/pipeline/final_archive_status.json'
HOST='root@62.238.127.235'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
     '-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','-o','ControlMaster=auto',
     '-o','ControlPersist=600','-o','ControlPath=/tmp/research-pull-%C']


def state(**values):
    values['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    p=STATE.with_suffix('.tmp');p.write_text(json.dumps(values,indent=2));p.replace(STATE)


def sync(source,target,excludes):
    target.mkdir(parents=True,exist_ok=True)
    cmd=['rsync','-rltpz','--partial','--partial-dir=.rsync-partial','--timeout=60',
         '--progress','--stats','-e',' '.join(SSH),*excludes,HOST+':'+source+'/',str(target)+'/']
    for attempt in range(1,9):
        state(phase='copying',source=source,attempt=attempt)
        print('COPY',source,'attempt',attempt,flush=True)
        p=subprocess.run(cmd)
        if p.returncode==0:return
        print('COPY retry, exit',p.returncode,flush=True)
        time.sleep(5)
    raise RuntimeError('Copy did not finish: '+source)


def log_destination(series,world,seed):
    if series.startswith('batch7-'):
        sub=Path('batch7-mn')/series[len('batch7-'):]
    elif series.startswith('batch8-survival50-'):
        sub=Path('batch8-survival50')/series[len('batch8-survival50-'):]
    elif series.startswith('batch9-survival50-'):
        sub=Path('batch9-survival50')/series[len('batch9-survival50-'):]
    else:raise RuntimeError('Unmapped server series: '+series)
    return ROOT/'logs'/sub/('seed-'+str(seed))


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


REMOTE_MANIFEST=r'''
import pathlib,os,json,hashlib,subprocess,stat
project=pathlib.Path('/root/Growth.covenant')
active=[x for x in subprocess.check_output(['ps','-eo','args'],text=True).splitlines() if x.startswith('/root/Growth.covenant/.venv/bin/python src/run.py')]
if active:raise SystemExit('Training is active; final archive is not stable')
count=0;total=0
for scope,base in [('project',project),('root',pathlib.Path('/root'))]:
 for folder,dirs,files in os.walk(base,followlinks=False):
  rel=pathlib.Path(folder).relative_to(base)
  if scope=='root' and rel==pathlib.Path('.'):
   dirs[:]=[d for d in dirs if d not in ('Growth.covenant','.ssh','.cache')]
  dirs.sort();files.sort()
  for name in list(dirs):
   path=pathlib.Path(folder)/name
   if path.is_symlink():
    print(json.dumps(dict(scope=scope,path=str(path.relative_to(base)),kind='symlink',target=os.readlink(path))),flush=True)
  for name in files:
   if name=='.DS_Store':continue
   path=pathlib.Path(folder)/name;localrel=str(path.relative_to(base))
   if path.is_symlink():
    print(json.dumps(dict(scope=scope,path=localrel,kind='symlink',target=os.readlink(path))),flush=True);continue
   if not path.is_file():raise RuntimeError('Unsupported file type: '+str(path))
   h=hashlib.sha256();size=0
   with path.open('rb') as f:
    for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block);size+=len(block)
   print(json.dumps(dict(scope=scope,path=localrel,kind='file',size=size,sha256=h.hexdigest())),flush=True)
   count+=1;total+=size
print(json.dumps(dict(kind='end',files=count,bytes=total)),flush=True)
'''


def verify(inventory):
    mapping={}
    for w in inventory['worlds']:
        dest=log_destination(w['series'],w['world'],w['seed'])
        header=json.loads((dest/'run.json').read_text())
        assert header['world_id']==w['world_id'] and header['sessions'][0]['seed']==w['seed']
        mapping[(w['series'],w['world'])]=dest
    manifest=ARCHIVE/'final_sha256_manifest.jsonl'
    errors=[];checked=0;checked_bytes=0;ended=None;links=0
    state(phase='verifying',checked_files=0,checked_bytes=0)
    stderr=(REPO/'.ai/pipeline/final_manifest_ssh.log').open('w')
    proc=subprocess.Popen(SSH+[HOST,'python3 -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,bufsize=1)
    proc.stdin.write(REMOTE_MANIFEST);proc.stdin.close()
    with manifest.open('w') as out:
        for line in proc.stdout:
            out.write(line)
            entry=json.loads(line)
            if entry['kind']=='end':ended=entry;continue
            rel=Path(entry['path'])
            if entry['scope']=='project' and rel.parts[0]=='logs':
                target=mapping[(rel.parts[1],rel.parts[2])].joinpath(*rel.parts[3:])
            else:
                target=ARCHIVE/('Growth.covenant' if entry['scope']=='project' else 'root-files')/rel
            try:
                if entry['kind']=='symlink':
                    if not target.is_symlink() or os.readlink(target)!=entry['target']:
                        errors.append('Symlink differs: '+str(target))
                    links+=1
                else:
                    if target.is_symlink() or target.stat().st_size!=entry['size'] or sha256(target)!=entry['sha256']:
                        errors.append('File differs: '+str(target))
                    checked+=1;checked_bytes+=entry['size']
            except OSError as e:errors.append(str(target)+': '+str(e))
            if checked and checked%1000==0:
                state(phase='verifying',checked_files=checked,checked_bytes=checked_bytes,mismatches=len(errors))
                print('VERIFIED',checked,'files,',checked_bytes,'bytes, mismatches',len(errors),flush=True)
    code=proc.wait();stderr.close()
    if code!=0 or ended is None:raise RuntimeError('Remote manifest failed, exit '+str(code))
    if errors:
        (ARCHIVE/'final_verification_errors.json').write_text(json.dumps(errors,indent=2))
        raise RuntimeError(str(len(errors))+' files differ; do not delete server')
    assert checked==ended['files'] and checked_bytes==ended['bytes']
    return dict(files=checked,bytes=checked_bytes,symlinks=links,worlds=len(mapping),manifest_sha256=sha256(manifest))


def main():
    ARCHIVE.mkdir(parents=True,exist_ok=True)
    subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    lock=(REPO/'.ai/pipeline/final_archive.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inventory=json.loads((REPO/'.ai/pipeline/final-server-inventory.json').read_text())
    assert not inventory['active']
    assert len(inventory['worlds'])==400
    sync('/root/Growth.covenant',ARCHIVE/'Growth.covenant',['--exclude=/logs/','--exclude=.DS_Store'])
    sync('/root',ARCHIVE/'root-files',['--exclude=/Growth.covenant/','--exclude=/.ssh/','--exclude=/.cache/','--exclude=.DS_Store'])
    result=verify(inventory)
    result.update(state='verified',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source='root@62.238.127.235:/root/Growth.covenant',
                  exclusions=['Operating system files outside /root','/root/.ssh','/root/.cache','.DS_Store'])
    (ARCHIVE/'final_backup_verified.json').write_text(json.dumps(result,indent=2))
    text='# Финальная копия проекта проверена\n\nВсе 400 миров текущего сервера сохранены в `research/logs/`. Остальные файлы проекта, модели, чекпоинты, окружение и файлы домашней папки root сохранены здесь.\n\nSHA-256 всех '+str(result['files'])+' обычных файлов совпали с сервером; проверено '+str(result['bytes'])+' байт. Символические ссылки внутри окружения также сверены.\n\nОбучение завершено. Сервер можно удалить после этой проверки. Системный образ ОС, SSH-настройки root и кэши не включены.\n'
    (ARCHIVE/'SAFE_TO_DELETE_SERVER.md').write_text(text)
    state(phase='complete',**result)
    print('FINAL ARCHIVE VERIFIED; SERVER DATA SAFE',json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        state(phase='failed',error=repr(e))
        raise
