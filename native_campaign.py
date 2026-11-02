"""Bounded, independent native Praetor volume campaign. Logs/artifacts only."""
import json,os,signal,subprocess,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
URL="http://127.0.0.1:8765"
def api(path,data=None):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    return json.loads(urllib.request.urlopen(URL+path,data=body,timeout=30).read())

def _harvest_rows(filename):
    try:
        return [s for s in Path(filename).read_text(errors='replace').splitlines()
                if s.strip() and s.count('\t') >= 2]
    except FileNotFoundError:
        return []

def _publish_harvest(arm, issue, previously_found, history, phase):
    """Report safe counts and gap/merit only. Never publish unpublished expressions."""
    token=os.environ.get('GH_TOKEN','')
    repo=os.environ.get('GITHUB_REPOSITORY','')
    found=_harvest_rows('FOUND.tsv')
    verified=_harvest_rows('VERIFIED.tsv')
    found_set=set(found)
    added=len(found_set - previously_found)
    ok=sum(s.endswith('\tOK') for s in verified)
    failed=sum(s.endswith('\tFAILED') for s in verified)
    now=time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime())
    row=f'| {now} | +{added} | {len(found_set)} | {ok} | {failed} |'
    next_history=(history+[row])[-25:]
    candidates=[]
    for line in found_set:
        fields=line.split('\t',2)
        try: candidates.append((float(fields[1]),int(fields[0])))
        except (ValueError,IndexError): pass
    best=sorted(candidates,reverse=True)[:5]
    best_text='\n'.join(f'- gap {gap:,}, merit {merit:.4f}' for merit,gap in best)
    body=('\n'.join([
        f'### hunter 15-minute harvest: {arm}',
        f'**phase:** {phase}  |  **run:** {os.environ.get("GITHUB_RUN_ID","?")} '
        f'| **shard:** {os.environ.get("HUNTER_SHARD","-")} '
        f'| **attempt:** {os.environ.get("GITHUB_RUN_ATTEMPT","1")}',
        '',
        'These are local job results. FOUND entries are candidates, not necessarily independently verified or submitted.',
        'Full prime expressions remain in the final job artifacts, not in this public issue.',
        '',
        '| checkpoint | new found | found total | verifier OK | verifier FAILED |',
        '|---|---:|---:|---:|---:|',
        *next_history,
        '',
        '**top candidate gap/merit pairs (no expressions):**',
        best_text or '- none yet',
        '',
        'The issue body is replaced every checkpoint to avoid notification spam.'
    ]))
    print('15min harvest',arm,'new',added,'total',len(found_set),
          'ok',ok,'failed',failed,flush=True)
    if not (token and repo):
        print('harvest: no github credentials; leaving only logs',flush=True)
        return issue,found_set,next_history
    slug=f'{arm} shard {os.environ.get("HUNTER_SHARD","-")}'
    title=f'Hunter harvest: run {os.environ.get("GITHUB_RUN_ID","?")} / {slug} / attempt {os.environ.get("GITHUB_RUN_ATTEMPT","1")}'
    suffix=f'/issues/{issue}' if issue else '/issues'
    payload={'body':body} if issue else {'title':title,'body':body}
    req=urllib.request.Request(
        f'https://api.github.com/repos/{repo}{suffix}',
        data=json.dumps(payload).encode(),
        headers={'Authorization':f'Bearer {token}',
                 'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28',
                 'Content-Type':'application/json',
                 'User-Agent':'hunter-harvest'},
        method='PATCH' if issue else 'POST')
    with urllib.request.urlopen(req,timeout=20) as response:
        updated=json.load(response)
    if not issue:
        issue=updated['number']
        print('harvest issue',updated['html_url'],flush=True)
    return issue,found_set,next_history

def main():
    arm=os.environ['HUNTER_ARM'];run=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    # Each workflow run reserves one million raw multipliers per family.
    # Retry attempts occupy a separate equally sized block.
    shard=int(os.environ['HUNTER_SHARD'])
    if not (1<=attempt<=9 and 0<=shard<=5):raise ValueError('unsupported retry or shard')
    base=run*100000000+attempt*10000000+shard*1000000+1
    if base+1000000>=2**64:raise ValueError('multiplier exceeds native word size')
    rows=[]
    for line in (ROOT/'cloud-state-template.tsv').read_text().splitlines():
        f=line.split('\t');f[4]=str(base);rows.append('\t'.join(f))
    (ROOT/'state.tsv').write_text('\n'.join(rows)+'\n')
    deadline=time.monotonic()+18000
    last_harvest=time.monotonic()
    harvest_issue=None
    previous_found=set()
    harvest_history=[]
    server=subprocess.Popen(['./hunter','serve','8765'],cwd=ROOT,stdout=open('native-server.log','a'),stderr=subprocess.STDOUT,start_new_session=True)
    try:
        for _ in range(120):
            if server.poll() is not None:raise RuntimeError('native server exited')
            try:api('/api/status');break
            except OSError:time.sleep(.5)
        else:raise RuntimeError('startup timeout')
        cores=max(1,os.cpu_count() or 2)
        print('campaign',dict(arm=arm,base=base,cores=cores,seconds=18000),flush=True)
        print(api('/api/start',dict(cores=cores,hours=5,job=60,gpu=0,arms=arm)),flush=True)
        while time.monotonic()<deadline:
            time.sleep(min(60,max(0,deadline-time.monotonic())))
            status=api('/api/status');Path('native-status.json').write_text(json.dumps(status,indent=2))
            print('checkpoint',status.get('found_session'),len(status.get('workers',[])),flush=True)
            if time.monotonic()-last_harvest>=900:
                try:
                    harvest_issue,previous_found,harvest_history=_publish_harvest(arm,harvest_issue,previous_found,harvest_history,'running')
                except Exception as exc:
                    print('harvest publication failed (search continues):',repr(exc),flush=True)
                last_harvest=time.monotonic()
    finally:
        try:
            harvest_issue,previous_found,harvest_history=_publish_harvest(arm,harvest_issue,previous_found,harvest_history,'final snapshot')
        except Exception as exc:
            print('final harvest publication failed:',repr(exc),flush=True)
        try:api('/api/stop',dict(now=1))
        except Exception:pass
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait()
        # Verifiers append independently. Stop only our own descendant verifier jobs.
        for line in subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines()[1:]:
            f=line.split(None,2)
            if len(f)==3 and f[2].startswith('hunter verify '):
                try:os.kill(int(f[0]),signal.SIGTERM)
                except ProcessLookupError:pass
if __name__=='__main__':main()
