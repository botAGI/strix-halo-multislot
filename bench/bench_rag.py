#!/usr/bin/env python3
"""RAG-realistic bench: 2-4K token prompts (shuffled corpus paragraphs, salted),
n_predict=128. Metrics per level: SERVER prompt processing p50/p95 (prompt_ms; queue wait NOT
included, this is NOT client TTFT), PP tok/s, decode per-stream p50, aggregate
decode tok/s over makespan. Historical non-streaming harness; for true client
TTFT use bench_rag_stream.py.
Usage: BENCH_BASE=... bench_rag.py 1,4,8,16 [window_s]"""
import itertools, os, random, statistics, sys, threading, time
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

def make_prompt(salt, target_paras):
    paras = [random.choice(PARAS) for _ in range(target_paras)]
    body = "\n\n".join(f"[Фрагмент {i+1}] {p}" for i, p in enumerate(paras))
    return (f"Сессия {salt}. Ниже выдержки из внутренней документации.\n\n{body}\n\n"
            "Вопрос: какие метрики важны при эксплуатации локального AI-стека и почему? Ответь кратко.")

def run_level(conc, window=90, target_paras=60):
    results, lock, errors = [], threading.Lock(), [0]
    salt_iter = itertools.count(random.randint(10**6, 10**7))
    start = time.perf_counter()
    stop_at = start + window

    def worker():
        sess = requests.Session()
        while time.perf_counter() < stop_at:
            prompt = make_prompt(next(salt_iter), target_paras)
            try:
                r = sess.post(f"{BASE}/completion", json={
                    "prompt": prompt, "n_predict": 128, "temperature": 0.6,
                    "top_p": 0.95, "cache_prompt": False}, timeout=600).json()
            except Exception:
                with lock:
                    errors[0] += 1
                continue
            with lock:
                if "timings" not in r:
                    errors[0] += 1
                    continue
                results.append((r["timings"], time.perf_counter()))

    with ThreadPoolExecutor(conc) as ex:
        futs = [ex.submit(worker) for _ in range(conc)]
        for f in futs:
            f.result()

    if not results:
        print(f"c={conc}: ALL FAILED ({errors[0]})", flush=True)
        return
    makespan = max(ts for _, ts in results) - start
    agg = sum(t["predicted_n"] for t, _ in results) / makespan
    prompt = sorted(t["prompt_ms"] for t, _ in results)
    pp = sorted(t["prompt_n"] / (t["prompt_ms"] / 1000) for t, _ in results)
    tps = sorted(t["predicted_per_second"] for t, _ in results)
    pn = statistics.median(t["prompt_n"] for t, _ in results)
    print(f"c={conc:>2}  err={errors[0]}  req={len(results):>3}  prompt_n~{pn:.0f}  "
          f"prompt p50={statistics.median(prompt)/1000:5.2f}s p95={prompt[max(0,int(len(prompt)*0.95)-1)]/1000:5.2f}s  "
          f"PP p50={statistics.median(pp):6.0f} tok/s  "
          f"decode p50={statistics.median(tps):5.1f}/поток  agg={agg:6.1f} tok/s", flush=True)

if __name__ == "__main__":
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    for c in [int(x) for x in sys.argv[1].split(",")]:
        run_level(c, window=win)
