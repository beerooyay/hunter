"""Bounded CPU portfolio for an owned POSIX machine; no automatic submissions.

Search slots are split approximately 70/20/10 across volume / merit 30 / merit 40.
Native verification can temporarily add processes, so these are not CPU quotas.
The existing native engine and research model remain unchanged.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
LIVE = 'https://primegaps.cloudygo.com/merits.txt'
ARMS = '6007.210,6007.2310,8009.210,8009.2310'
VERSION = 'portfolio-v1'


def atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


def save(path: Path, value: dict) -> None:
    atomic(path, json.dumps(value, indent=2, allow_nan=False) + '\n')


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def split_slots(slots: int) -> tuple[int, int, int]:
    if not 3 <= slots <= 64:
        raise ValueError('slots must be 3..64')
    thirty = max(1, round(slots * .2))
    forty = max(1, round(slots * .1))
    return slots - thirty - forty, thirty, forty


def parse_records(text: str, minimum: int = 1) -> dict[int, float]:
    records = {}
    for line in text.splitlines():
        f = line.split()
        if not f or not f[0].isdigit():
            continue
        if len(f) < 2:
            raise ValueError('malformed record row')
        gap, merit = int(f[0]), float(f[1])
        if gap < 1 or not math.isfinite(merit) or merit < 0:
            raise ValueError('invalid record row')
        records[gap] = max(merit, records.get(gap, 0.))
    if len(records) < minimum:
        raise ValueError(f'only {len(records)} valid rows; need {minimum}')
    return records


def refresh(state: Path) -> dict[int, float]:
    request = urllib.request.Request(LIVE, headers={'User-Agent': 'hunter-portfolio/1'})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(16_000_001)
    if len(raw) < 1_000_000:
        raise ValueError('record download is unexpectedly small')
    if len(raw) > 16_000_000:
        raise ValueError('record download unexpectedly large')
    text = raw.decode('utf-8')
    records = parse_records(text, minimum=10_000)
    atomic(state / 'upstream.txt', text)
    save(state / 'upstream.json', dict(source=LIVE, fetched_at=time.time(),
         sha256=hashlib.sha256(raw).hexdigest(), rows=len(records)))
    return records


def native_verified(folder: Path):
    """Match gap AND expression; never treat FOUND alone as a verified record."""
    ok = set()
    verify = folder / 'VERIFIED.tsv'
    if verify.exists():
        for line in verify.read_text().splitlines():
            f = line.split('\t')
            if len(f) >= 4 and f[0].isdigit() and f[3] == 'OK':
                ok.add((int(f[0]), f[2]))
    found = folder / 'FOUND.tsv'
    if found.exists():
        for line in found.read_text().splitlines():
            f = line.split('\t')
            if len(f) >= 3 and f[0].isdigit() and (int(f[0]), f[2]) in ok:
                yield int(f[0]), float(f[1]), f[2]


def local_verified(state: Path):
    yield from native_verified(state / 'volume')
    # This queue is written before research verification starts and survives timeouts.
    for path in sorted((state / 'verification').glob('*.json')):
        item = load(path)
        if item.get('status') == 'ok':
            yield int(item['gap']), float(item['merit']), item['start']


def publish_records(state: Path, upstream: dict[int, float], folders: list[Path]):
    records = dict(upstream)
    for gap, merit, _ in local_verified(state):
        records[gap] = max(records.get(gap, 0.), merit)
    text = ''.join(f'{gap}\t{merit:.10f}\n' for gap, merit in sorted(records.items()))
    for folder in folders:
        atomic(folder / 'records.txt', text)
    atomic(state / 'known-records.txt', text)
    return records


def initialize_native(state: Path, template: Path, base: int) -> bool:
    if state.exists():
        return False
    if not 1 <= base < 2**63 - 1_000_000_000:
        raise ValueError('unsafe multiplier base')
    lines = []
    for line in template.read_text().splitlines():
        fields = line.split('\t')
        if len(fields) < 5:
            raise ValueError('invalid native state template')
        fields[4] = str(base)
        lines.append('\t'.join(fields))
    atomic(state, '\n'.join(lines) + '\n')
    return True


def api(port: int, path: str, data: dict | None = None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', data=body, timeout=3) as r:
        return json.load(r)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in
            ('HUNTER_GPU', 'HUNT_DRY', 'HUNT_MSK', 'HUNTER_PATTERNS')}


def stop_process(p: subprocess.Popen, grace: float = 10) -> None:
    if p.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=5)


def queue_candidate(queue: Path, left, right) -> Path:
    import gmpy2
    start, gap = str(left), int(right - left)
    key = hashlib.sha256(f'{start}:{gap}'.encode()).hexdigest()
    path = queue / (key + '.json')
    if not path.exists():
        with gmpy2.context(precision=160):
            merit = float(gmpy2.mpfr(gap) / gmpy2.log(left))
        save(path, dict(start=start, gap=gap, merit=merit, status='pending',
             created_at=time.time(), verification='BPSW and next_prime; not a certificate'))
    return path


def verify_file(path: Path) -> bool:
    import gmpy2
    item = load(path)
    p = gmpy2.mpz(item['start'])
    q = p + item['gap']
    ok = bool(gmpy2.is_bpsw_prp(p) and gmpy2.is_bpsw_prp(q)
              and gmpy2.next_prime(p) == q)
    item.update(status='ok' if ok else 'failed', checked_at=time.time())
    save(path, item)
    return ok


def verify_bounded(path: Path, seconds: float) -> bool:
    item = load(path)
    if item['status'] in ('ok', 'failed'):
        return item['status'] == 'ok'
    if seconds <= 0:
        raise TimeoutError('verification remains queued')
    # subprocess.run kills/reaps its child on timeout or any interrupted wait.
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '_verify', str(path)],
                   check=False, timeout=seconds)
    return load(path)['status'] == 'ok'


def target_worker(args) -> None:
    """Reuse the existing model, but isolate targets, histories, and verification."""
    import moon
    import research
    lane = args.lane.resolve()
    lane.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + args.seconds
    research.ROOT = lane
    moon.root = lane
    research.TARGETS = (args.target,)
    digest = hashlib.sha256((ROOT / 'research.py').read_bytes() +
                           (ROOT / 'moon.py').read_bytes()).hexdigest()[:12]
    research.VERSION = f'{VERSION}-target-{args.target}-{digest}'
    original_verify = moon.verify

    def durable_verify(left, right):
        candidate = queue_candidate(args.queue, left, right)
        return verify_bounded(candidate, end - time.monotonic())

    moon.verify = durable_verify
    try:
        settings = argparse.Namespace(state=lane / 'learning', seed=args.seed,
                    seconds=args.seconds, keep=3, scout=256)
        research.run(settings)
    finally:
        moon.verify = original_verify


def pending_native(folder: Path) -> list[dict]:
    done = set()
    path = folder / 'VERIFIED.tsv'
    if path.exists():
        for line in path.read_text().splitlines():
            f = line.split('\t')
            if len(f) >= 4 and f[0].isdigit() and f[3] in ('OK', 'FAILED'):
                done.add((int(f[0]), f[2]))
    pending = []
    path = folder / 'FOUND.tsv'
    if path.exists():
        for line in path.read_text().splitlines():
            f = line.split('\t')
            if len(f) >= 3 and f[0].isdigit() and (int(f[0]), f[2]) not in done:
                pending.append(dict(gap=int(f[0]), merit=float(f[1]), expression=f[2]))
    return pending


def check_host(slots: int) -> None:
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') != 'self-hosted':
        raise RuntimeError('full campaigns require an owned machine or self-hosted runner; use CI for tests')
    available = os.cpu_count() or 1
    if slots > max(1, available - 2):
        raise RuntimeError(f'{slots} search slots would leave fewer than two of {available} CPUs free')


def run_portfolio(args) -> None:
    check_host(args.slots)
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'portfolio.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (state / 'STOP').exists():
            raise RuntimeError('STOP exists; remove it explicitly before restarting')
        nv, n30, n40 = split_slots(args.slots)
        binary = ROOT / 'hunter'
        # Resolve Python dependencies before starting any search processes.
        import gmpy2, moon, research
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError('build hunter first with ./build.sh')
        targets = [(t, i, state / f'target-{t}-{i}')
                   for t, n in ((30, n30), (40, n40)) for i in range(n)]
        volume = state / 'volume'
        folders = [volume] + [p for _, _, p in targets]
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            # Native serve changes directory to its executable. A real copy avoids
            # accidentally writing into the user's main hunter directory.
            shutil.copy2(binary, folder / 'hunter')
            if (ROOT / 'ui.html').exists():
                shutil.copy2(ROOT / 'ui.html', folder / 'ui.html')
        initialize_native(volume / 'state.tsv', ROOT / 'cloud-state-template.tsv',
                          int(time.time()) * 100_000_000 + 1)
        upstream = refresh(state)  # Fail closed at startup; never silently use stale records.
        publish_records(state, upstream, folders)
        os.nice(5)
        seconds = int(args.hours * 3600)
        started = time.time()
        end = time.monotonic() + seconds
        port = free_port()
        children = []
        logs = []
        snapshot = dict(version=VERSION, pid=os.getpid(), status='starting',
                        started_at=started, search_ends_at=started + seconds,
                        hard_ends_at=started + seconds + args.drain + 60,
                        search_slots=dict(volume=nv, merit30=n30, merit40=n40),
                        note='search slots, not CPU quotas; native verification can add processes',
                        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                        native_port=port)
        save(state / 'status.json', snapshot)
        def terminate(signum, frame):
            raise KeyboardInterrupt('stop requested')
        signal.signal(signal.SIGTERM, terminate)
        status = 'completed'
        try:
            out = (volume / 'server.log').open('a')
            logs.append(out)
            server = subprocess.Popen([str(volume / 'hunter'), 'serve', str(port)],
                     cwd=volume, env=clean_env(), stdout=out, stderr=subprocess.STDOUT,
                     start_new_session=True)
            children.append(server)
            for _ in range(120):
                if server.poll() is not None:
                    raise RuntimeError('native server exited; inspect volume/server.log')
                try:
                    api(port, '/api/status')
                    break
                except OSError:
                    time.sleep(.25)
            else:
                raise RuntimeError('native startup timed out')
            response = api(port, '/api/start', dict(cores=nv, hours=args.hours,
                           job=300, gpu=0, arms=ARMS))
            if isinstance(response, dict) and response.get('ok') is False:
                raise RuntimeError(f'native start rejected: {response}')
            # Resume unfinished native verification from the previous session.
            api(port, '/api/verify', {})
            for target, index, folder in targets:
                seed_path = folder / 'seed.json'
                seed = load(seed_path, {}).get('seed')
                if seed is None:
                    seed = int.from_bytes(os.urandom(8), 'big')
                    save(seed_path, {'seed': seed})
                out = (folder / 'worker.log').open('a')
                logs.append(out)
                command = [sys.executable, str(Path(__file__).resolve()), '_target',
                           '--target', str(target), '--seconds', str(max(1, int(end-time.monotonic()))),
                           '--seed', str(seed), '--lane', str(folder),
                           '--queue', str(state / 'verification')]
                children.append(subprocess.Popen(command, cwd=ROOT, env=clean_env(),
                                stdout=out, stderr=subprocess.STDOUT, start_new_session=True))
            snapshot['children'] = [p.pid for p in children]
            snapshot['status'] = 'running'
            save(state / 'status.json', snapshot)
            last_table = 0.
            while time.monotonic() < end and not (state / 'STOP').exists():
                for child in children:
                    if child.poll() is not None and (child.returncode != 0 or end-time.monotonic() > 15):
                        raise RuntimeError(f'worker {child.pid} exited early ({child.returncode})')
                snapshot['native'] = api(port, '/api/status')
                snapshot['research'] = {folder.name: load(folder / 'learning/summary.json', {})
                                        for _, _, folder in targets}
                if time.monotonic() - last_table > 300:
                    publish_records(state, upstream, folders)
                    last_table = time.monotonic()
                snapshot['updated_at'] = time.time()
                save(state / 'status.json', snapshot)
                time.sleep(min(10, max(0, end - time.monotonic())))
            if (state / 'STOP').exists():
                status = 'stopped'
        except KeyboardInterrupt:
            status = 'stopped'
        except BaseException as error:
            status = f'error: {error}'
            raise
        finally:
            # Stop new searches first. Leave native verifiers alive for a bounded drain.
            for child in children[1:]:
                stop_process(child)
            deadline = time.monotonic() + (args.drain if status == 'completed' else 0)
            if children and children[0].poll() is None:
                with contextlib.suppress(Exception):
                    api(port, '/api/stop', dict(now=1))
                deadline = time.monotonic() + (args.drain if status == 'completed' else 0)
                with contextlib.suppress(Exception):
                    api(port, '/api/verify', {})
                while time.monotonic() < deadline:
                    if not pending_native(volume):
                        break
                    time.sleep(min(2, max(0, deadline-time.monotonic())))
                stop_process(children[0])
            if status == 'completed':
                # Retry research candidates left pending by a previous deadline.
                # Use only the remaining shared drain budget.
                for candidate in sorted((state / 'verification').glob('*.json')):
                    if time.monotonic() >= deadline:
                        break
                    if load(candidate)['status'] == 'pending':
                        with contextlib.suppress(subprocess.TimeoutExpired, TimeoutError):
                            verify_bounded(candidate, deadline - time.monotonic())
            # All native candidates already live in FOUND.tsv. This manifest is
            # an explicit backlog, not an assertion that pending candidates passed.
            save(state / 'native-pending.json', dict(candidates=pending_native(volume)))
            for out in logs:
                out.close()
            publish_records(state, upstream, folders)
            best = {}
            for gap, merit, expr in local_verified(state):
                if gap not in best or merit > best[gap][0]:
                    best[gap] = (merit, expr)
            atomic(state / 'verified-candidates.tsv', ''.join(
                f'{g}\t{m:.8f}\t{e}\n' for g, (m, e) in sorted(best.items())))
            snapshot.update(status=status, stopped_at=time.time(), updated_at=time.time(),
                 pending_native=len(pending_native(volume)),
                 pending_research=sum(load(p)['status']=='pending'
                                      for p in (state/'verification').glob('*.json')))
            save(state / 'status.json', snapshot)
            print(json.dumps(snapshot, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--hours', type=float, default=5.)
    run.add_argument('--slots', type=int, default=10)
    run.add_argument('--drain', type=int, default=300)
    run.add_argument('--state', type=Path, default=ROOT / 'build/portfolio')
    target = commands.add_parser('_target')
    target.add_argument('--target', type=int, choices=(30,40), required=True)
    target.add_argument('--seconds', type=int, required=True)
    target.add_argument('--seed', type=int, required=True)
    target.add_argument('--lane', type=Path, required=True)
    target.add_argument('--queue', type=Path, required=True)
    verify = commands.add_parser('_verify')
    verify.add_argument('path', type=Path)
    inspect = commands.add_parser('status')
    inspect.add_argument('--state', type=Path, default=ROOT / 'build/portfolio')
    plan = commands.add_parser('plan')
    plan.add_argument('--slots', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'run':
        if not 0 < args.hours <= 24 or not 0 <= args.drain <= 600:
            parser.error('hours must be >0 and <=24; drain 0..600 seconds')
        split_slots(args.slots)
        run_portfolio(args)
    elif args.command == '_target':
        if not 1 <= args.seconds <= 86400:
            parser.error('target seconds must be 1..86400')
        target_worker(args)
    elif args.command == '_verify':
        raise SystemExit(0 if verify_file(args.path) else 2)
    elif args.command == 'status':
        info = load(args.state / 'status.json', {'status': 'not started'})
        if info.get('status') == 'running':
            try:
                os.kill(info['pid'], 0)
            except ProcessLookupError:
                info['status'] = 'not running; last checkpoint below'
        print(json.dumps(info, indent=2))
    else:
        a,b,c = split_slots(args.slots)
        print(json.dumps(dict(volume=a, merit30=b, merit40=c,
                         verification='extra native processes; not hard CPU quotas'), indent=2))


if __name__ == '__main__':
    main()
