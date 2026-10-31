"""Bounded CPU frontier: find large probable primes, never claim world records."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import signal
import time
import gmpy2

STOP = False
def stop(*_):
    global STOP
    STOP = True

def write(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--state", type=Path, default=Path("campaign/frontier.json"))
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    path = args.state
    path.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(path.read_text()) if path.exists() else {
        "version": 1, "tested": 0, "probable_primes": 0, "best_bits": 0,
        "best_hex": None, "best_sha256": None, "total_search_seconds": 0,
        "note": "BPSW + GMP probable prime tests; NOT mathematical certificates or world records",
    }
    import hashlib
    rng = random.Random(int.from_bytes(os.urandom(16), "big"))
    begin = time.monotonic()
    limit = begin + max(1, args.seconds)
    sizes = (4096, 8192, 16384, 32768, 65536)
    # Move to the next experimental size only after a probable prime was located.
    index = min(len(sizes)-1, sum(state["best_bits"] >= s for s in sizes))
    bits = sizes[index]
    state["current_bits"] = bits
    clock = 0
    try:
        while not STOP and time.monotonic() < limit:
            candidate = rng.getrandbits(bits) | (1 << (bits-1)) | 1
            state["tested"] += 1
            # Fast small-prime rejection before expensive GMP probable-prime tests.
            if not any(candidate % p == 0 for p in (3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97)):
                if gmpy2.is_bpsw_prp(candidate) and gmpy2.is_prime(candidate, 25):
                    state["probable_primes"] += 1
                    if bits > state["best_bits"]:
                        value = format(candidate, "x")
                        state.update(best_bits=bits, best_hex=value,
                                     best_sha256=hashlib.sha256(bytes.fromhex(("0" if len(value)%2 else "")+value)).hexdigest())
                        index = min(len(sizes)-1, index+1)
                        bits = sizes[index]
                        state["current_bits"] = bits
                        print("large probable prime found:", state["best_bits"], "bits", flush=True)
            if time.monotonic()-clock >= 5:
                state["updated"] = time.time()
                write(path,state)
                clock = time.monotonic()
    finally:
        state["total_search_seconds"] += max(0.,time.monotonic()-begin)
        state["updated"] = time.time()
        state["status"] = "segment finished"
        write(path, state)

if __name__ == "__main__":
    main()
