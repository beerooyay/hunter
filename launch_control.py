"""Start only the local control services. Searches are started from the UI."""
import os,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for port,args,logname in [(8766,[str(ROOT/'hunter'),'serve','8766'],'server.log'),(8767,[sys.executable,str(ROOT/'control_room.py')],'control.log'),(8768,[sys.executable,str(ROOT/'phone_view.py')],'phone.log')]:
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/'+('api/status' if port==8766 else 'control/status'),timeout=2)
        print(f'{port}: already responding');continue
    except OSError:pass
    with (ROOT/logname).open('ab') as log:
        p=subprocess.Popen(args,cwd=ROOT,env=dict(os.environ,HUNTER_NO_OPEN='1'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(f'{port}: started pid {p.pid}')
print('http://127.0.0.1:8767/')
