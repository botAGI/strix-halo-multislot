#!/usr/bin/env python3
"""RAG-like bench with STREAMING: measures true client TTFT (first content chunk
arrival, queue included) alongside server prompt_ms from the final chunk timings.
Usage: BENCH_BASE=... bench_rag_stream.py 1,4,8,16 [window_s]"""
import itertools, json, os, random, statistics, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = os.environ.get("BENCH_BASE", "http://localhost:8080")

PARAS = [
    "Локальный AI-стек на собственном железе избавляет от передачи корпоративных документов внешним провайдерам, но требует продуманной эксплуатации: обновлений образов, мониторинга и резервного копирования.",
    "Векторная база хранит эмбеддинги фрагментов документов; при запросе пользователя система ищет ближайшие фрагменты по косинусной близости и передаёт их языковой модели как контекст.",
    "Реранкер уточняет порядок найденных фрагментов: кросс-энкодер оценивает пару запрос-документ целиком и отсеивает ложные совпадения, которые эмбеддинги пропустили.",
    "Мониторинг инференс-сервера строится вокруг трёх метрик: время до первого токена, скорость генерации на поток и суммарная пропускная способность узла под конкурентной нагрузкой.",
    "Квантизация весов до четырёх бит сокращает объём памяти втрое против половинной точности; качество ответов при этом падает незначительно для большинства прикладных задач.",
    "Оркестрация контейнеров описывает сервисы декларативно: рестарт-политики, лимиты памяти, порядок запуска и проверки здоровья задаются в одном файле и воспроизводятся на любом узле.",
    "Единая память процессора и графики в новых мини-ПК позволяет держать модель на десятки гигабайт без дискретной видеокарты, но пропускная способность шины становится главным ограничителем.",
    "Резервное копирование стека включает дампы баз данных, снапшоты томов и экспорт конфигураций; восстановление проверяется регулярными учениями, а не предположениями.",
]

def make_prompt(salt, target_paras=60):
    paras = [random.choice(PARAS) for _ in range(target_paras)]
    body = "\n\n".join(f"[Фрагмент {i+1}] {p}" for i, p in enumerate(paras))
    return (f"Сессия {salt}. Ниже выдержки из внутренней документации.\n\n{body}\n\n"
            "Вопрос: какие метрики важны при эксплуатации локального AI-стека и почему? Ответь кратко.")

def one_request(sess, salt):
    prompt = make_prompt(salt)
    t0 = time.perf_counter()
    ttft = None
    final = None
    with sess.post(f"{BASE}/completion", json={
            "prompt": prompt, "n_predict": 128, "temperature": 0.6,
            "top_p": 0.95, "cache_prompt": False, "stream": True},
            timeout=600, stream=True) as r:
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            chunk = json.loads(line[6:])
            if ttft is None and chunk.get("content"):
                ttft = time.perf_counter() - t0
            if chunk.get("stop"):
                final = chunk
    if ttft is None or final is None or "timings" not in final:
        return None
    t = final["timings"]
    return dict(client_ttft=ttft, prompt_ms=t["prompt_ms"], prompt_n=t["prompt_n"],
                pred=t["predicted_n"], tps=t["predicted_per_second"],
                total=time.perf_counter() - t0)

def run_level(conc, window=90):
    results, lock, errors = [], threading.Lock(), [0]
    salt_iter = itertools.count(random.randint(10**6, 10**7))
    start = time.perf_counter()
    stop_at = start + window

    def worker():
        sess = requests.Session()
        while time.perf_counter() < stop_at:
            try:
                m = one_request(sess, next(salt_iter))
            except Exception:
                m = None
            with lock:
                if m is None:
                    errors[0] += 1
                else:
                    results.append((m, time.perf_counter()))

    with ThreadPoolExecutor(conc) as ex:
        futs = [ex.submit(worker) for _ in range(conc)]
        for f in futs:
            f.result()

    if not results:
        print(f"c={conc}: ALL FAILED ({errors[0]})", flush=True)
        return
    makespan = max(ts for _, ts in results) - start
    agg = sum(m["pred"] for m, _ in results) / makespan
    prefill_agg = sum(m["prompt_n"] for m, _ in results) / makespan
    ct = sorted(m["client_ttft"] for m, _ in results)
    pm = sorted(m["prompt_ms"] / 1000 for m, _ in results)
    tot = sorted(m["total"] for m, _ in results)
    pn = statistics.median(m["prompt_n"] for m, _ in results)
    print(f"c={conc:>2}  err={errors[0]}  req={len(results):>3}  prompt_n~{pn:.0f}  "
          f"клиентский TTFT p50={statistics.median(ct):5.2f}s p95={ct[max(0,int(len(ct)*0.95)-1)]:5.2f}s  "
          f"(серверный prompt p50={statistics.median(pm):5.2f}s)  "
          f"полный ответ p50={statistics.median(tot):5.1f}s  agg={agg:6.1f} tok/s  "
          f"prefill=Σprompt_n/makespan={prefill_agg:6.0f} tok/s (makespan={makespan:.1f}s)", flush=True)

if __name__ == "__main__":
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    for c in [int(x) for x in sys.argv[1].split(",")]:
        run_level(c, window=win)
