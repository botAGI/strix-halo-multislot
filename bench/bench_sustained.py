#!/usr/bin/env python3
"""Sustained multi-slot load: c=32 for N minutes, per-minute aggregate tok/s.
Usage: BENCH_BASE=http://host:port bench_sustained.py [minutes]
Prints one line per minute: tokens generated in that bucket / 60s."""
import itertools, os, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = os.environ.get("BENCH_BASE", "http://localhost:8080")
MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 30
CONC = 32
TASKS = [
    "Напиши HTML-страницу с игрой «угадай число» на чистом JS.",
    "Напиши функцию на Python, которая валидирует IBAN.",
    "Опиши архитектуру очереди задач на Redis в пяти абзацах.",
    "Напиши SQL-схему для трекера привычек с комментариями.",
    "Сочини короткую техническую заметку про мониторинг GPU.",
    "Напиши bash-скрипт ротации логов с проверками ошибок.",
]

lock = threading.Lock()
buckets = {}  # minute index -> [tokens, requests]
errors = [0]
start = time.perf_counter()
stop_at = start + MINUTES * 60


def worker(salt_iter):
    sess = requests.Session()
    while time.perf_counter() < stop_at:
        prompt = f"Сессия {next(salt_iter)}. {random.choice(TASKS)}"
        try:
            r = sess.post(f"{BASE}/completion", json={
                "prompt": prompt, "n_predict": 128, "temperature": 0.6,
                "top_p": 0.95, "cache_prompt": False}, timeout=600).json()
        except Exception:
            with lock:
                errors[0] += 1
            continue
        now = time.perf_counter()
        with lock:
            if "timings" not in r:
                errors[0] += 1
                continue
            b = int((now - start) // 60)
            buckets.setdefault(b, [0, 0])
            buckets[b][0] += r["timings"]["predicted_n"]
            buckets[b][1] += 1


def reporter():
    last = -1
    while time.perf_counter() < stop_at + 5:
        time.sleep(10)
        cur = int((time.perf_counter() - start) // 60)
        with lock:
            for b in sorted(buckets):
                if last < b < cur:
                    tok, req = buckets[b]
                    print(f"min {b + 1:>2}: {tok / 60:6.1f} tok/s  req={req}  err_total={errors[0]}",
                          flush=True)
                    last = b


if __name__ == "__main__":
    rt = threading.Thread(target=reporter, daemon=True)
    rt.start()
    salt_iter = itertools.count(random.randint(10**6, 10**7))
    with ThreadPoolExecutor(CONC) as ex:
        futs = [ex.submit(worker, salt_iter) for _ in range(CONC)]
        for f in futs:
            f.result()
    total_tok = sum(v[0] for v in buckets.values())
    total_req = sum(v[1] for v in buckets.values())
    span = time.perf_counter() - start
    print(f"ИТОГ: {total_tok} токенов, {total_req} запросов, {errors[0]} ошибок, "
          f"{span / 60:.1f} мин, средний агрегат {total_tok / span:.1f} tok/s", flush=True)
