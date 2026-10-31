"""Orchestrate a bounded free-only Hunter campaign; checkpoint every ~15 minutes."""
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "campaign"
ISSUE = "repos/beerooyay/hunter/issues/1/comments"
END = dt.datetime.fromisoformat("2026-11-01T21:19:00+00:00")
TICK = 900
STOP = threading.Event()

def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}

def append(path, entry):
    with Path(path).open("a") as f:
        f.write(json.dumps(entry, separators=(",",":")) + "\n")

def report(text):
    print(text, flush=True)
    append(DATA / "checkpoints.jsonl", dict(timestamp=dt.datetime.now(dt.timezone.utc).isoformat(), message=text))
    if os.getenv("GH_TOKEN"):
        try:
            subprocess.run(["gh", "api", ISSUE, "-X", "POST", "-f", "body="+text],
                           timeout=45, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True)
        except Exception as exc:
            print("github issue update failed:", exc, flush=True)

def stop_process(p):
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=20)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

def moon_loop(deadline):
    index = sum(1 for _ in (DATA / "moon.jsonl").open()) if (DATA / "moon.jsonl").exists() else 0
    while not STOP.is_set() and time.monotonic() + 45 < deadline:
        # Rotate target tiers as an independent parallel experiment.
        merit = (30,40,50,43)[index % 4]
        seed = 403100 + index * 113
        seconds = min(590, max(30,int(deadline-time.monotonic()-30)))
        old = set((ROOT / "build").glob("moon-*/summary.json"))
        command = [sys.executable, "-u", str(ROOT/"moon.py"), "--seconds", str(seconds),
                   "--merit", str(merit), "--seed", str(seed), "--keep", "4"]
        with (DATA / "moon.log").open("a") as logs:
            process = subprocess.Popen(["nice","-n","12",*command],cwd=ROOT,
                         stdout=logs,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                process.wait(timeout=seconds+15)
            except subprocess.TimeoutExpired:
                stop_process(process)
        summaries = set((ROOT/"build").glob("moon-*/summary.json"))-old
        result = load(max(summaries, key=lambda p:p.stat().st_mtime)) if summaries else {}
        append(DATA/"moon.jsonl",dict(index=index,merit=merit,seed=seed,exit=process.returncode,
                  status=result.get("status"),scouted=result.get("scouted"),
                  tested=result.get("tested"),best=result.get("best"),records=result.get("records"),
                  targets=result.get("targets"),timestamp=time.time()))
        index += 1

def line_count(path):
    try:
        with Path(path).open() as f:
            return sum(1 for _ in f)
    except OSError:
        return 0

def checkpoint(label, research, frontier):
    summary = load(DATA/"learning"/"summary.json")
    large = load(DATA/"frontier.json")
    recent = {}
    try:
        with (DATA/"moon.jsonl").open() as f:
            for line in f:
                recent = json.loads(line)
    except (OSError,ValueError):
        pass
    lanes = summary.get("lanes",{})
    aimed = lanes.get("aimed",{})
    control = lanes.get("control",{})
    text = (
        f"### hunter checkpoint: {label} (utc)\n"
        f"- adaptive praetor research: \`{summary.get('status','no report')}\` / {summary.get('phase','pending')}; "
        f"jobs={summary.get('jobs',0)}, local verified improvements={summary.get('records',0)}\n"
        f"- aimed trials: {aimed.get('tested',0)}, best merit={aimed.get('best',0):.4f}; "
        f"random controls: {control.get('tested',0)}, best merit={control.get('best',0):.4f}\n"
        f"- moon independent test: last target merit={recent.get('merit','-')}, "
        f"candidates={recent.get('tested','-')}, local improvements={recent.get('records','-')}, "
        f"best merit={recent.get('best','-')}\n"
        
        f"- processes: research={research.poll() if research.poll() is not None else 'running'}, "
        f"frontier={frontier.poll() if frontier is not None and frontier.poll() is not None else ('not launched' if frontier is None else 'running')}\n"
        f"- tests are exploratory. endpoint BPSW + next_prime is not a certificate; "
        f"table improvements are against a local snapshot, not necessarily current global records."
    )
    report(text)

def main():
    DATA.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    remain = int((END-now).total_seconds())
    if remain <= 0:
        report("24-hour campaign deadline reached; no additional compute launched.")
        return
    # Host runner hard limit is 6 hours. Leave time for clean exit and artifact upload.
    duration = min(remain, 5*3600+18*60)
    if duration < 45:
        report("Campaign deadline too close to launch a safe new segment.")
        return
    (DATA/"run-info.json").write_text(json.dumps(dict(utc=now.isoformat(),segment_seconds=duration,
                                              github_run=os.getenv("GITHUB_RUN_ID")),indent=2)+"\n")
    research_cmd = [sys.executable,"-u",str(ROOT/"research.py"),"--seconds",str(duration),
                    "--state",str(DATA/"learning"),"--seed","3050"]
    frontier_cmd = None
    with (DATA/"research.log").open("a") as log1, (DATA/"frontier.log").open("a") as log2:
        research = subprocess.Popen(["nice","-n","10",*research_cmd],cwd=ROOT,
                       stdout=log1,stderr=subprocess.STDOUT,start_new_session=True)
        frontier = None
        deadline=time.monotonic()+duration
        moon = threading.Thread(target=moon_loop,args=(deadline,),daemon=True)
        moon.start()
        report(f"### campaign compute started\nrun={os.getenv('GITHUB_RUN_ID','local')}, "
               f"planned segment={duration//60} min; stop no later than {END.isoformat()}. "
               "two independent prime-gap merit experimental lanes on free standard linux cpu.")
        try:
            i=0
            while time.monotonic()<deadline:
                seconds=min(TICK,deadline-time.monotonic())
                if seconds>0: STOP.wait(seconds)
                if STOP.is_set(): break
                i+=1
                checkpoint(f"+{15*i} min",research,frontier)
                if research.poll() is not None:
                    report("research worker exited early; see research.log. segment ending without declaring success.")
                    break
        finally:
            STOP.set()
            stop_process(research)
            stop_process(frontier)
            moon.join(timeout=35)
            checkpoint("segment complete",research,frontier)

if __name__=="__main__":
    main()
