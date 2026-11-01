"""Run the original record-yield Praetor engine on a bounded Linux runner."""
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
END = dt.datetime.fromisoformat("2026-11-01T21:23:22+00:00")
ISSUE = "repos/beerooyay/hunter/issues/1/comments"
URL = "http://127.0.0.1:8765"

def api(path, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(URL+path, data=body), timeout=15) as response:
        return response.read().decode()

def count(path):
    try:
        return sum(1 for x in path.read_text().splitlines() if x.strip())
    except FileNotFoundError:
        return 0

def report(message):
    print(message, flush=True)
    if os.environ.get("GH_TOKEN"):
        subprocess.run(["gh", "api", ISSUE, "-X", "POST", "-f", "body="+message],
                       check=False, timeout=30)

def main():
    remaining = (END - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining < 120:
        print("campaign deadline reached", flush=True)
        return
    duration = min(remaining, 5*3600)
    server = subprocess.Popen(["./hunter", "serve", "8765"], cwd=ROOT,
                              stdout=open("native-server.log", "a"),
                              stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(40):
            if server.poll() is not None:
                raise RuntimeError("native hunter server exited during startup")
            try:
                api("/api/status")
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("native hunter server did not respond")
        # Prefer record-yield optimizer and use all available CPU cores, reserving one for orchestration.
        cores = max(1, (os.cpu_count() or 2)-1)
        hours = max(1, int((duration+3599)//3600))
        result = api("/api/start", {"cores":cores,"hours":hours,"job":10,"gpu":0,"arms":""})
        report("### native record-first campaign started\n"
               f"Praetor record-yield engine; {cores} CPU cores, {int(duration//60)} min segment. "
               f"API response: {result[:300]}")
        start = time.monotonic()
        while time.monotonic()-start < duration:
            time.sleep(min(900, max(0, duration-(time.monotonic()-start))))
            status = api("/api/status")
            Path("native-status.json").write_text(status)
            report(f"### record-first checkpoint +{int((time.monotonic()-start)//60)} min\n"
                   f"FOUND.tsv rows={count(ROOT/'FOUND.tsv')}; "
                   f"VERIFIED.tsv rows={count(ROOT/'VERIFIED.tsv')}; "
                   f"jobs.tsv rows={count(ROOT/'jobs.tsv')}. "
                   "These are file counts, not certified global records.")
    finally:
        try:
            api("/api/stop", {"now":1})
        except Exception:
            pass
        os.killpg(server.pid, signal.SIGTERM)
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)

if __name__ == "__main__":
    main()
