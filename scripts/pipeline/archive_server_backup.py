#!/usr/bin/env python3
"""Resume the project archive in its final location; retry interrupted rsync."""
from pathlib import Path
import subprocess
import time
import json
import datetime

root=Path.home()/'Desktop/research'
dest=root/'archive/server-62.238.127.235'
dest.mkdir(parents=True,exist_ok=True)
ssh='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o ControlMaster=auto -o ControlPersist=600 -o ControlPath=/tmp/research-pull-%C'
for source,sub,excludes in [('/root/Growth.covenant','Growth.covenant',['--exclude=/logs/','--exclude=.DS_Store']),('/root','root-files',['--exclude=/Growth.covenant/','--exclude=/.ssh/','--exclude=/.cache/'])]:
    target=dest/sub;target.mkdir(exist_ok=True)
    for attempt in range(8):
        cmd=['rsync','-rlt','--partial','--timeout=60','--stats','-e',ssh,*excludes,'root@62.238.127.235:'+source+'/',str(target)+'/']
        print('Archive',source,'attempt',attempt+1,flush=True)
        p=subprocess.run(cmd)
        if p.returncode==0:break
        time.sleep(5)
    else:raise SystemExit('Backup failed: '+source)
status={'state':'copied','finished_at':datetime.datetime.now().isoformat(),'note':'Logs checked separately; archive copied incrementally. Running training may create newer checkpoints and models after the file list was captured.'}
(dest/'copy_status.json').write_text(json.dumps(status,indent=2))
print('SERVER ARCHIVE COPY COMPLETE',flush=True)
