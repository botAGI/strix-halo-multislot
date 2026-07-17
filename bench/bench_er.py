#!/usr/bin/env python3
"""Embed/rerank concurrency sweep, target via env (Strix-B bench servers).
Usage: BENCH_URL=http://host:port/v1/embeddings bench_er.py payload.json 4,16,32 [duration]
Per level: warmup 5s, timed window, latencies -> p50/p95, RPS, errors."""
import json, os, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor

import requests

URL = os.environ["BENCH_URL"]
PAYLOAD = json.load(open(sys.argv[1]))
LABEL = os.path.basename(sys.argv[1]).replace(".json", "")


def worker(stop_at, lat, errs):
    sess = requests.Session()
    while time.perf_counter() < stop_at:
        t0 = time.perf_counter()
        try:
            r = sess.post(URL, json=PAYLOAD, timeout=120)
            ok = r.status_code == 200
        except Exception:
            ok = False
        dt = (time.perf_counter() - t0) * 1000
        (lat if ok else errs).append(dt)


def run_level(conc, duration=45, warmup=5):
    s = requests.Session()
    end = time.perf_counter() + warmup
    while time.perf_counter() < end:
        try:
            s.post(URL, json=PAYLOAD, timeout=120)
        except Exception:
            pass
    lat, errs = [], []
    stop_at = time.perf_counter() + duration
    with ThreadPoolExecutor(conc) as ex:
        futs = [ex.submit(worker, stop_at, lat, errs) for _ in range(conc)]
        for f in futs:
            f.result()
    lat.sort()
    n = len(lat)
    if n == 0:
        print(f"{LABEL} c={conc}: ALL FAILED ({len(errs)} errors)", flush=True)
        return
    p50 = statistics.median(lat)
    p95 = lat[max(0, int(n * 0.95) - 1)]
    print(f"{LABEL:8} c={conc:>2}  n={n:>5}  rps={n / duration:7.1f}  "
          f"p50={p50:7.1f}ms  p95={p95:7.1f}ms  max={lat[-1]:8.1f}ms  err={len(errs)}",
          flush=True)


if __name__ == "__main__":
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else 45
    for c in [int(x) for x in sys.argv[2].split(",")]:
        run_level(c, duration=dur)
