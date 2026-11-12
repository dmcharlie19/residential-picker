"""Serve /residential on vibrationpanel.ru without changing neighboring routes."""
from pathlib import Path
from datetime import datetime, timezone
import shutil
import subprocess

configs=[Path('/home/jj/gateway/conf.d/vibrationpanel.conf'),Path('/home/jj/gateway/conf.d/portfolio-balancer.conf')]
before={p:p.read_text() for p in configs}
legacy='    location = /residential {\n        return 301 /residential/;\n    }\n\n    location ^~ /residential/ {\n        set $residential_upstream http://residential-picker-frontend:80;\n        rewrite ^/residential/(.*)$ /$1 break;\n        proxy_pass $residential_upstream;\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n\n'
block="""    location = /residential {
        return 301 /residential/;
    }

    location ^~ /residential/ {
        resolver 127.0.0.11 valid=10s;
        set $residential_upstream http://residential-picker-frontend:80;
        rewrite ^/residential/(.*)$ /$1 break;
        proxy_pass $residential_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

"""
vibration,portfolio=configs
after=dict(before)
marker='    location / {\n        auth_basic "Restricted";'
if 'location ^~ /residential/' not in after[vibration]:
    if after[vibration].count(marker)!=1:
        raise RuntimeError('Unexpected vibration gateway config; nothing changed')
    after[vibration]=after[vibration].replace(marker,block+marker)
if legacy in after[portfolio]:
    after[portfolio]=after[portfolio].replace(legacy,'',1)
changed=[p for p in configs if after[p]!=before[p]]
if not changed:
    print('Gateway routes already configured; unchanged.')
    raise SystemExit(0)
backup_dir=Path('/home/jj/residential-picker/backups')
backup_dir.mkdir(exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
for p in changed:
    shutil.copy2(p,backup_dir/(p.name+'.'+stamp))
    tmp=p.with_suffix('.pending')
    tmp.write_text(after[p])
    tmp.replace(p)
try:
    subprocess.run(['docker','exec','gateway-nginx','nginx','-t'],check=True)
    subprocess.run(['docker','exec','gateway-nginx','nginx','-s','reload'],check=True)
except BaseException:
    for p in changed:
        p.write_text(before[p])
    subprocess.run(['docker','exec','gateway-nginx','nginx','-t'],check=True)
    subprocess.run(['docker','exec','gateway-nginx','nginx','-s','reload'],check=True)
    raise
print('Enabled https://vibrationpanel.ru/residential/. Backups:',backup_dir)
