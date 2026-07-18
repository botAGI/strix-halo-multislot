#!/usr/bin/env python3
"""Multi-slot generation sweep against llama-server --parallel 32 on Strix-B.
Per level: N workers issue unique salted prompts (cache_prompt=false), n_predict=128.
Metrics: aggregate tok/s (sum predicted_n / makespan), per-stream tps, TTFT p50."""
import itertools, json, random, statistics, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

import requests

import os
BASE = os.environ.get("BENCH_BASE", "http://localhost:8080")
N_PREDICT = int(os.environ.get("N_PREDICT", "128"))
TASKS = [
    "Напиши HTML-страницу с игрой «угадай число» на чистом JS.",
    "Напиши функцию на Python, которая валидирует IBAN.",
    "Опиши архитектуру очереди задач на Redis в пяти абзацах.",
    "Напиши SQL-схему для трекера привычек с комментариями.",
    "Сочини короткую техническую заметку про мониторинг GPU.",
    "Напиши bash-скрипт ротации логов с проверками ошибок.",
]

def one_request(sess, salt):
    prompt = f"Сессия {salt}. {random.choice(TASKS)}"
    t0 = time.perf_counter()
    r = sess.post(f"{BASE}/completion", json={
        "prompt": prompt, "n_predict": N_PREDICT, "temperature": 0.6,
        "top_p": 0.95, "cache_prompt": False}, timeout=600).json()
    wall = time.perf_counter() - t0
    if "timings" not in r:
        return None
    t = r["timings"]
    return dict(pred=t["predicted_n"], tps=t["predicted_per_second"],
                prompt_ms=t["prompt_ms"], wall=wall)

def run_level(conc, window=75):
    results, lock, errors = [], threading.Lock(), [0]
    salt_iter = itertools.count(random.randint(10**6, 10**7))
    start = time.perf_counter()
    stop_at = start + window

    def worker():
        sess = requests.Session()
        while time.perf_counter() < stop_at:
            m = one_request(sess, next(salt_iter))
            with lock:
                if m is None:
                    errors[0] += 1
                else:
                    results.append((m, time.perf_counter()))

    with ThreadPoolExecutor(conc) as ex:
        futs = [ex.submit(worker) for _ in range(conc)]
        for f in futs:
            f.result()

    makespan = max(ts for _, ts in results) - start
    total_pred = sum(m["pred"] for m, _ in results)
    agg = total_pred / makespan
    tps = sorted(m["tps"] for m, _ in results)
    prompt = sorted(m["prompt_ms"] for m, _ in results)
    print(f"c={conc:>2}  err={errors[0]}  req={len(results):>4}  agg={agg:7.1f} tok/s  "
          f"per-stream p50={statistics.median(tps):5.1f} min={tps[0]:5.1f}  "
          f"prompt p50={statistics.median(prompt):6.0f}ms p95={prompt[int(len(prompt)*0.95)-1]:6.0f}ms",
          flush=True)

if __name__ == "__main__":
    for c in [int(x) for x in sys.argv[1].split(",")]:
        run_level(c)
